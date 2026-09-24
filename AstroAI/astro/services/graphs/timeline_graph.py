# astro/services/timeline_graph_threads.py
from __future__ import annotations
from typing import TypedDict, Any, Dict, List, Optional, Tuple
from datetime import date
import os
from concurrent.futures import ThreadPoolExecutor
from utils.select_dasha import filter_dasha_by_horizon

from langgraph.graph import StateGraph, START, END
from astro.services.parsers.timeline_parsers import (
    TLBaselineBundle,
    ADInfo,
    ADNote,
    PDCardText,
    PDInfo,
    ADTimelineItem,
    TimelinePayload,
)
from astro.models import PromptTemplate
from astro.services.llm import create_llm_chain

MAX_WORKERS_DEFAULT = int(os.getenv("TL_MAX_WORKERS", "4"))

DOMAIN_PRIMARY_HOUSES = {
    "career": [10, 2, 11],
    "love": [7, 2, 11],
    "health": [1, 6],
    "finance": [2, 11, 10],
}
DOMAIN_VARGAS = {
    "career": ["D10"],
    "love": ["D9"],
    "health": ["D30"],
    "finance": ["D2"],
}
# ===========================
#        GRAPH STATE
# ===========================
class TLState(TypedDict, total=False):
    # Inputs
    today: str
    dashas: List[Dict[str, Any]]
    charts: Dict[str, Any]
    shadbala: Dict[str, Any]
    ashtakavarga: Dict[str, Any]
    max_workers: int
    user: Any  # Django User instance

    # Outputs
    baseline: Dict[str, Any]
    ad_notes: List[Dict[str, Any]]
    timeline_items: List[Dict[str, Any]]
    timeline_payload: Dict[str, Any]


# ===========================
#        HELPERS
# ===========================
def _select_current_ad(dashas: List[Dict[str, Any]], today: str) -> ADInfo:
    t = today or date.today().isoformat()
    for d in dashas:
        ad = d.get("antardashas", {})
        if not ad:
            continue
        s, e = ad.get("start", "9999-12-31"), ad.get("end", "0001-01-01")
        if s <= t <= e:
            return ADInfo(lord=ad.get("lord", "unknown"), start=s, end=e)
    first = (dashas[0] or {}).get("antardashas", {})
    return ADInfo(
        lord=first.get("lord", "unknown"),
        start=first.get("start", "unknown"),
        end=first.get("end", "unknown"),
    )


def _ad_key(ad_like: Dict[str, Any]) -> str:
    return (
        f'{ad_like.get("lord","?")}|{ad_like.get("start","?")}|{ad_like.get("end","?")}'
    )


def _domain_slice(baseline: Dict[str, Any], domain: str) -> Dict[str, Any]:
    domains = baseline.get("domains", [])
    found = next((d for d in domains if d.get("domain") == domain), None)
    if found:
        return found
    return {
        "domain": domain,
        "primary_houses": DOMAIN_PRIMARY_HOUSES[domain],
        "grade": "Mixed",
        "varga_used": DOMAIN_VARGAS[domain],
        "varga_grade": None,
        "varga_confirmation": "Neutral",
        "notes": [],
        "risks": [],
    }


# ===========================
#        NODES
# ===========================
def tl_baseline_node(state: TLState) -> TLState:
    charts = state.get("charts", {}) or {}
    vargas = {k: charts[k] for k in charts.keys() if k in {"D9", "D10", "D30", "D2"}}
    tl_baseline_chain = create_llm_chain(
        parser=TLBaselineBundle,
        prompt_template=PromptTemplate.objects.get(name="timeline_baseline_prompt"),
        metadata={"user": state.get("user"), "chain_type": "timeline_baseline"},
    )
    out = tl_baseline_chain.invoke(
        {
            "d1_chart": charts.get("D1", {}),
            "ashtakavarga": state.get("ashtakavarga", {}) or {},
            "shadbala": state.get("shadbala", {}) or {},
            "vargas": vargas,
            "primary_house_map": DOMAIN_PRIMARY_HOUSES,
        }
    ).model_dump()
    return {"baseline": out}


def tl_ad_notes_node(state: TLState) -> TLState:
    """Parallel AD notes for ALL Antardashas using ThreadPoolExecutor.map."""
    charts = state.get("charts", {}) or {}
    lagna_hint = charts.get("D1", {}).get("lagna", "unknown")
    max_workers = state.get("max_workers", MAX_WORKERS_DEFAULT)

    # Build ordered list of AD infos
    ad_infos: List[Dict[str, Any]] = []
    for entry in state["dashas"]:
        ad = entry.get("antardashas", {})
        ad_infos.append(
            ADInfo(
                lord=ad.get("lord", "unknown"),
                start=ad.get("start", "unknown"),
                end=ad.get("end", "unknown"),
            ).model_dump()
        )

    def worker(ad_info: Dict[str, Any]) -> Dict[str, Any]:
        ad_note_chain = create_llm_chain(
            parser=ADNote,
            prompt_template=PromptTemplate.objects.get(name="timeline_ad_note_prompt"),
            metadata={"user": state.get("user"), "chain_type": "timeline_ad_note"},
        )
        res = ad_note_chain.invoke(
            {
                "today": state["today"],
                "current_ad": ad_info,
                "baseline": state["baseline"],
                "lagna_hint": lagna_hint,
            }
        ).model_dump()
        note = res.get("note", "")

        return {"antardasha": ad_info, "note": note}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        notes = list(ex.map(worker, ad_infos))  # preserves order
    return {"ad_notes": notes}


def tl_build_timeline_node(state: TLState) -> TLState:
    """Parallel PD micro-cards across ALL PDs under ALL ADs (ThreadPoolExecutor.map)."""
    baseline = state["baseline"]
    charts = state.get("charts", {}) or {}
    max_workers = state.get("max_workers", MAX_WORKERS_DEFAULT)

    baseline_domains = {
        "career": _domain_slice(baseline, "career"),
        "love": _domain_slice(baseline, "love"),
        "health": _domain_slice(baseline, "health"),
        "finance": _domain_slice(baseline, "finance"),
    }

    # Flatten metadata for all PD tasks
    metas: List[Dict[str, Any]] = []
    for entry in state["dashas"]:
        ad = entry.get("antardashas", {})
        ad_info = ADInfo(
            lord=ad.get("lord", "unknown"),
            start=ad.get("start", "unknown"),
            end=ad.get("end", "unknown"),
        ).model_dump()
        ad_key = _ad_key(ad_info)
        for pd in ad.get("pratyantardashas", []) or []:
            pd_info = PDInfo(
                lord=pd.get("lord", "unknown"),
                start=pd.get("start", "unknown"),
                end=pd.get("end", "unknown"),
            ).model_dump()
            metas.append({"ad_key": ad_key, "ad_info": ad_info, "pd_info": pd_info})

    def pd_worker(meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """Returns (ad_key, pd_info, micro_dict)"""
        ad_info = meta["ad_info"]
        pd_info = meta["pd_info"]

        pd_micro_chain = create_llm_chain(
            parser=PDCardText,
            prompt_template=PromptTemplate.objects.get(name="timeline_pd_micro_prompt"),
            metadata={"user": state.get("user"), "chain_type": "timeline_pd_micro"},
        )

        res = pd_micro_chain.invoke(
            {
                "parent_ad": ad_info,
                "pd": pd_info,
                "baseline_domains": baseline_domains,
                "charts_hint": {
                    "D1": charts.get("D1", {}),
                    "D9": charts.get("D9", {}),
                    "D10": charts.get("D10", {}),
                    "D30": charts.get("D30", {}),
                    "D2": charts.get("D2", {}),
                },
            }
        ).model_dump()

        return meta["ad_key"], pd_info, res

    # Run all PD workers in parallel
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    if metas:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for ad_key, pd_info, micro in ex.map(
                pd_worker, metas
            ):  # preserves metas order
                grouped.setdefault(ad_key, []).append({"info": pd_info, "micro": micro})

    # Rebuild ordered items per input dashas
    items: List[Dict[str, Any]] = []
    for entry in state["dashas"]:
        ad = entry.get("antardashas", {})
        ad_info = ADInfo(
            lord=ad.get("lord", "unknown"),
            start=ad.get("start", "unknown"),
            end=ad.get("end", "unknown"),
        ).model_dump()
        key = _ad_key(ad_info)
        items.append({"antardasha": ad_info, "pratyantardashas": grouped.get(key, [])})

    return {"timeline_items": items}


def tl_assemble_node(state: TLState) -> TLState:
    # Index AD notes by key
    notes_index = {
        _ad_key(n.get("antardasha", {})): n.get("note", "")
        for n in state.get("ad_notes", [])
    }

    # Attach notes to each item
    items_with_notes = []
    for it in state.get("timeline_items", []):
        ad = it["antardasha"]
        note = notes_index.get(_ad_key(ad), "")
        items_with_notes.append(
            ADTimelineItem(
                antardasha=ADInfo(**ad),
                note=note,
                pratyantardashas=it["pratyantardashas"],
            ).model_dump()
        )

    # Top banner current AD + note
    current_ad = _select_current_ad(state["dashas"], state["today"]).model_dump()
    current_note = notes_index.get(_ad_key(current_ad), "")

    payload = TimelinePayload(
        current_antardasha=ADInfo(**current_ad),
        current_ad_note=current_note,
        antardashas=[ADTimelineItem(**it) for it in items_with_notes],
    ).model_dump()
    return {"timeline_payload": payload}


# ===========================
#        BUILD GRAPH
# ===========================
def build_timeline_graph_threads():
    g = StateGraph(TLState)
    g.add_node("P1_BASELINE", tl_baseline_node)
    g.add_node("P2_AD_NOTES_ALL", tl_ad_notes_node)  # parallel inside (threads)
    g.add_node("P3_PD_MICROS_ALL", tl_build_timeline_node)  # parallel inside (threads)
    g.add_node("P4_ASSEMBLE", tl_assemble_node)

    g.add_edge(START, "P1_BASELINE")
    g.add_edge("P1_BASELINE", "P2_AD_NOTES_ALL")
    g.add_edge("P1_BASELINE", "P3_PD_MICROS_ALL")
    g.add_edge("P2_AD_NOTES_ALL", "P4_ASSEMBLE")
    g.add_edge("P3_PD_MICROS_ALL", "P4_ASSEMBLE")
    g.add_edge("P4_ASSEMBLE", END)
    return g.compile()


# ===========================
#         RUNNER
# ===========================
def run_timeline_graph(
    user,
    today_iso: Optional[str] = date.today().isoformat(),
    max_workers: int = MAX_WORKERS_DEFAULT,
) -> Dict[str, Any]:
    """
    Sync runner using ThreadPoolExecutor.map for parallel LLM calls.
    """

    dashas = filter_dasha_by_horizon(
        user.charts.vimsottari_dhasa,
        layers=["AD", "PD"],
        thresholds={"years": 5},
        flatten=True,
    )
    charts = user.charts.charts
    shadbala = user.charts.shadbala
    ashtakavarga = user.charts.ashtaka_varga
    app = build_timeline_graph_threads()
    s: TLState = {
        "today": today_iso or date.today().isoformat(),
        "dashas": dashas,
        "charts": charts or {},
        "shadbala": shadbala or {},
        "ashtakavarga": ashtakavarga or {},
        "max_workers": max_workers,
        "user": user,
    }
    for event in app.stream(s):
        for _, payload in event.items():
            s.update(payload)

    return {
        "timeline": s.get("timeline_payload", {}),
        "debug": {
            "baseline": s.get("baseline", {}),
            "ad_notes_count": len(s.get("ad_notes", [])),
            "items_count": len(s.get("timeline_items", [])),
            "max_workers": s.get("max_workers"),
        },
    }
