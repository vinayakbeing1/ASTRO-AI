from __future__ import annotations
from typing import Any, Dict, Optional
from datetime import date
from django.contrib.auth.models import User
from utils.select_dasha import find_current_and_next
from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from astro.services.parsers.profile_parsers import (
    SectionsBundle,
    HomeMiniPayload,
    BaselineBundleLite,
    TodayLine,
    CareerMoneySection,
    RelationshipsLoveSection,
    HealthEnergySection,
    SpiritualSection,
)
from astro.models import PromptTemplate

from astro.services.llm import create_llm_chain

# ---------------------------
# Graph state
# ---------------------------
class HomeState(TypedDict, total=False):
    # Inputs
    today_iso: str
    today_only: bool
    selected_periods: Dict[
        str, Dict[str, Dict[str, str]]
    ]  # {"antardasha": {current,next}, "sookshmadasha": {current}}
    charts: Dict[str, Any]
    shadbala: Dict[str, Any]
    ashtakavarga: Dict[str, Any]
    lucky_defaults: Dict[str, str]

    # Step outputs
    baseline: Dict[str, Any]
    headline_line: str
    career_section: Dict[str, Any]
    love_section: Dict[str, Any]
    health_section: Dict[str, Any]
    spiritual_section: Dict[str, Any]

    # Final
    home_payload: Dict[str, Any]


DOMAIN_PRIMARY_HOUSES = {
    "career_money": [10, 2, 11],
    "relationships_love": [7, 2, 11],
    "health_energy": [1, 6],
    "spiritual": [9, 12],
}
DOMAIN_VARGAS = {
    "career_money": ["D10", "D2"],
    "relationships_love": ["D9"],
    "health_energy": ["D30"],
    "spiritual": ["D20"],
}

LUCKY_DEFAULTS = {"day": "Thursday", "color": "Yellow"}
# ---------------------------
# Helpers
# ---------------------------
VARGA_KEYS = (
    set().union(*DOMAIN_VARGAS.values())
    if DOMAIN_VARGAS
    else {"D2", "D9", "D10", "D20", "D30"}
)


def _domain_slice(baseline: Dict[str, Any], domain: str) -> Dict[str, Any]:
    # Fallback if baseline result is missing that domain
    if not baseline or "domains" not in baseline:
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
    return next(
        (d for d in baseline["domains"] if d["domain"] == domain),
        {
            "domain": domain,
            "primary_houses": DOMAIN_PRIMARY_HOUSES[domain],
            "grade": "Mixed",
            "varga_used": DOMAIN_VARGAS[domain],
            "varga_grade": None,
            "varga_confirmation": "Neutral",
            "notes": [],
            "risks": [],
        },
    )


# ---------------------------
# Nodes
# ---------------------------
def baseline_node(state: HomeState) -> HomeState:
    charts = state.get("charts", {}) or {}
    vargas_subset = {k: charts[k] for k in charts.keys() if k in VARGA_KEYS}
    baseline_chain = create_llm_chain(
        parser=BaselineBundleLite,
        prompt_template=PromptTemplate.objects.get(name="profile_baseline_prompt"),
        metadata={"user": state.get("user"), "chain_type": "profile_baseline"},
    )

    out = baseline_chain.invoke(
        {
            "d1_chart": charts.get("D1", {}),
            "ashtakavarga": state.get("ashtakavarga", {}) or {},
            "shadbala": state.get("shadbala", {}) or {},
            "vargas": vargas_subset,
        }
    )
    return {"baseline": out}


def headline_node(state: HomeState) -> HomeState:
    sd_cur = (state["selected_periods"].get("sookshmadasha", {}) or {}).get(
        "current", {}
    )

    headline_chain = create_llm_chain(
        parser=TodayLine,
        prompt_template=PromptTemplate.objects.get(name="profile_headline_prompt"),
        metadata={"user": state.get("user"), "chain_type": "profile_headline"},
    )

    out = headline_chain.invoke(
        {
            "today": state["today_iso"],
            "sookshma_cur": sd_cur,
            "lagna_hint": state.get("charts", {}).get("D1", {}).get("lagna", "unknown"),
        }
    )
    return {"headline_line": out.line}


def career_node(state: HomeState) -> HomeState:
    ad_cur = (state["selected_periods"]["antardasha"] or {}).get("current", {})
    ad_next = (state["selected_periods"]["antardasha"] or {}).get("next", {})
    base = _domain_slice(state.get("baseline", {}), "career_money")
    charts = state.get("charts", {})

    career_chain = create_llm_chain(
        parser=CareerMoneySection,
        prompt_template=PromptTemplate.objects.get(name="profile_career_prompt"),
        metadata={"user": state.get("user"), "chain_type": "profile_career"},
    )
    out = career_chain.invoke(
        {
            "baseline": base,
            "ad_cur": ad_cur,
            "ad_next": ad_next,
            "charts": {
                "D10": charts.get("D10", {}),
                "D2": charts.get("D2", {}),
                "D1": charts.get("D1", {}),
            },
        }
    )
    return {"career_section": out}


def love_node(state: HomeState) -> HomeState:
    ad_cur = (state["selected_periods"]["antardasha"] or {}).get("current", {})
    ad_next = (state["selected_periods"]["antardasha"] or {}).get("next", {})
    base = _domain_slice(state.get("baseline", {}), "relationships_love")
    charts = state.get("charts", {})

    love_chain = create_llm_chain(
        parser=RelationshipsLoveSection,
        prompt_template=PromptTemplate.objects.get(name="profile_love_prompt"),
        metadata={"user": state.get("user"), "chain_type": "profile_love"},
    )
    out = love_chain.invoke(
        {
            "baseline": base,
            "ad_cur": ad_cur,
            "ad_next": ad_next,
            "charts": {"D9": charts.get("D9", {}), "D1": charts.get("D1", {})},
        }
    )
    return {"love_section": out}


def health_node(state: HomeState) -> HomeState:
    ad_cur = (state["selected_periods"]["antardasha"] or {}).get("current", {})
    ad_next = (state["selected_periods"]["antardasha"] or {}).get("next", {})
    base = _domain_slice(state.get("baseline", {}), "health_energy")
    charts = state.get("charts", {})

    health_chain = create_llm_chain(
        parser=HealthEnergySection,
        prompt_template=PromptTemplate.objects.get(name="profile_health_prompt"),
        metadata={"user": state.get("user"), "chain_type": "profile_health"},
    )
    out = health_chain.invoke(
        {
            "baseline": base,
            "ad_cur": ad_cur,
            "ad_next": ad_next,
            "charts": {"D30": charts.get("D30", {}), "D1": charts.get("D1", {})},
        }
    )
    return {"health_section": out}


def spiritual_node(state: HomeState) -> HomeState:
    ad_cur = (state["selected_periods"]["antardasha"] or {}).get("current", {})
    base = _domain_slice(state.get("baseline", {}), "spiritual")
    charts = state.get("charts", {})
    spiritual_chain = create_llm_chain(
        parser=SpiritualSection,
        prompt_template=PromptTemplate.objects.get(name="profile_spiritual_prompt"),
        metadata={"user": state.get("user"), "chain_type": "profile_spiritual"},
    )
    out = spiritual_chain.invoke(
        {
            "baseline": base,
            "ad_cur": ad_cur,
            "charts": {"D20": charts.get("D20", {}), "D1": charts.get("D1", {})},
            "lucky_defaults": state.get("lucky_defaults", LUCKY_DEFAULTS),
        }
    )
    return {"spiritual_section": out}


def assemble_node(state: HomeState) -> HomeState:
    payload = HomeMiniPayload(
        today_for_you=state["headline_line"],
        sections=SectionsBundle(
            career_money=state["career_section"],
            relationships_love=state["love_section"],
            health_energy=state["health_section"],
            spiritual=state["spiritual_section"],
        ),
    ).model_dump()
    return {"home_payload": payload}


# ---------------------------
# Build graph (Baseline → parallel fan-out → Assemble)
# ---------------------------
def build_home_sections_graph() -> StateGraph[HomeState]:
    g = StateGraph(HomeState)

    # Only HEADLINE path (no baseline/sections)
    g.add_node("HEADLINE", headline_node)
    g.add_node("BASELINE", baseline_node)
    g.add_node("CAREER", career_node)
    g.add_node("LOVE", love_node)
    g.add_node("HEALTH", health_node)
    g.add_node("SPIRITUAL", spiritual_node)
    g.add_node("ASSEMBLE", assemble_node)

    g.add_conditional_edges(
        START, lambda s: s.get("today_only"), {True: "HEADLINE", False: "BASELINE"}
    )

    # Parallel after Baseline
    g.add_edge("BASELINE", "HEADLINE")
    g.add_edge("BASELINE", "CAREER")
    g.add_edge("BASELINE", "LOVE")
    g.add_edge("BASELINE", "HEALTH")
    g.add_edge("BASELINE", "SPIRITUAL")

    # Assemble waits for all
    g.add_conditional_edges(
        "HEADLINE", lambda s: s.get("today_only"), {True: END, False: "ASSEMBLE"}
    )
    g.add_edge("CAREER", "ASSEMBLE")
    g.add_edge("LOVE", "ASSEMBLE")
    g.add_edge("HEALTH", "ASSEMBLE")
    g.add_edge("SPIRITUAL", "ASSEMBLE")

    g.add_edge("ASSEMBLE", END)
    return g.compile()


app = build_home_sections_graph()
# ---------------------------
# Runner
# ---------------------------
def build_home_sections(
    today_iso: str,
    selected_periods: Dict[str, Dict[str, Dict[str, str]]],
    charts: Optional[Dict[str, Dict]] = None,
    shadbala: Optional[Dict] = None,
    ashtakavarga: Optional[Dict] = None,
    lucky_defaults: Optional[Dict[str, str]] = None,
    today_only: bool = False,
) -> Dict[str, Any]:
    """
    Parallel pipeline:
      1) BASELINE (D1 + SAV + Shadbala + Vargas)
      2) HEADLINE (Sookshmadasha current), CAREER/LOVE/HEALTH/SPIRITUAL (Antardasha current + next) — in parallel
      3) ASSEMBLE

    Returns: {"home": HomeMiniPayload, "debug": {...}}
    """
    state: HomeState = {
        "today_iso": today_iso,
        "today_only": today_only,
        "selected_periods": selected_periods,
        "charts": charts or {},
        "shadbala": shadbala or {},
        "ashtakavarga": ashtakavarga or {},
        "lucky_defaults": lucky_defaults or LUCKY_DEFAULTS,
    }
    for event in app.stream(state):
        for _, payload in event.items():
            state.update(payload)

    if today_only:
        return {"today_for_you": state["headline_line"]}

    return state.get("home_payload", {})


def run_profile_graph(
    user: User,
    today_only: bool = False,
) -> Dict[str, Any]:
    selected_periods = {
        "antardasha": find_current_and_next(
            user.charts.vimsottari_dhasa, date.today(), level="antardasha"
        ),
        "sookshmadasha": find_current_and_next(
            user.charts.vimsottari_dhasa, date.today(), level="sookshmadasha"
        ),
    }

    home_payload = build_home_sections(
        today_iso=date.today().isoformat(),
        selected_periods=selected_periods,
        charts=user.charts.charts,
        shadbala=user.charts.shadbala,
        ashtakavarga=user.charts.ashtaka_varga,
        lucky_defaults={"day": "Friday", "color": "White"},
        today_only=today_only,
    )

    return home_payload
