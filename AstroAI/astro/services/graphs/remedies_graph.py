# astro/services/remedies_graph.py
from __future__ import annotations
from datetime import date
from typing import TypedDict, Any, Dict, List, Optional, Tuple
import os
from concurrent.futures import ThreadPoolExecutor
from langgraph.graph import StateGraph, START, END
from django.conf import settings
from astro.services.llm import create_llm_chain
from utils.select_dasha import filter_dasha_by_horizon
from astro.models import PromptTemplate
from astro.services.parsers.remedies_parsers import DiagnosisLite, PlanLite
from utils.select_dasha import find_current_and_next

MAX_WORKERS_DEFAULT = int(os.getenv("REMEDIES_MAX_WORKERS", "16"))

# ============================================================
# Graph State
# ============================================================
class RemediesState(TypedDict, total=False):
    charts: Dict[str, Any]  # needs charts["D1"] minimally
    shadbala: Dict[str, Any]  # {"planets":{"Saturn":{"pct_req":...}}}
    ashtakavarga: Dict[str, Any]  # {"sarva_by_sign": {...}}
    dasha_focus: Dict[
        str, Any
    ]  # {"antardasha":{"current":{"lord","start","end"},"next":{...}}}
    profile_prefs: Optional[
        Dict[str, Any]
    ]  # {"religion","diet","time_per_day_min","budget_weekly_usd","gemstone_policy"}

    diagnosis: Dict[str, Any]
    plan: Dict[str, Any]


def diagnose_node(state: RemediesState) -> RemediesState:
    charts = state.get("charts", {}) or {}
    diagnose_chain = create_llm_chain(
        parser=DiagnosisLite,
        prompt_template=PromptTemplate.objects.get(name="remedies_diagnose_prompt"),
        metadata={"user": state.get("user"), "chain_type": "remedies_diagnose"},
    )
    out = diagnose_chain.invoke(
        {
            "d1_chart": charts.get("D1", {}),
            "shadbala": state.get("shadbala", {}) or {},
            "ashtakavarga": state.get("ashtakavarga", {}) or {},
            "profile_prefs": state.get("profile_prefs", {}) or {},
        }
    ).model_dump()
    return {"diagnosis": out}


def plan_node(state: RemediesState) -> RemediesState:
    ad = (state.get("dasha_focus", {}) or {}).get("antardasha", {}) or {}
    cur = ad.get("current", {}) or {}
    nxt = ad.get("next", {}) or {}
    plan_chain = create_llm_chain(
        parser=PlanLite,
        prompt_template=PromptTemplate.objects.get(name="remedies_plan_prompt"),
        metadata={"user": state.get("user"), "chain_type": "remedies_plan"},
    )
    out = plan_chain.invoke(
        {
            "targets": state["diagnosis"]["targets"],
            "ad_current": cur,
            "ad_next": nxt,
            "profile_prefs": state.get("profile_prefs", {}) or {},
        }
    ).model_dump()
    return {"plan": out}


# =========================
# Graph
# =========================
def build_remedies_two_call_graph():
    g = StateGraph(RemediesState)
    g.add_node("DIAGNOSE_LITE", diagnose_node)
    g.add_node("PLAN_LITE", plan_node)
    g.add_edge(START, "DIAGNOSE_LITE")
    g.add_edge("DIAGNOSE_LITE", "PLAN_LITE")
    g.add_edge("PLAN_LITE", END)
    return g.compile()


# =========================
# Runner
# =========================
def run_remedies_graph(
    *, user, profile_prefs: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Minimal inputs:
      charts.D1, shadbala.pct_req, ashtakavarga.sarva_by_sign
      dasha_focus: antardasha current (+ next optional)
    Output:
      {"diagnosis": DiagnosisLite, "plan": PlanLite}
    """
    antardasha = find_current_and_next(
        user.charts.vimsottari_dhasa, date.today(), level="antardasha"
    )
    state: RemediesState = {
        "charts": user.charts.charts or {},
        "shadbala": user.charts.shadbala or {},
        "ashtakavarga": user.charts.ashtaka_varga or {},
        "dasha_focus": {"antardasha": antardasha},
        "profile_prefs": profile_prefs or {},
    }
    app = build_remedies_two_call_graph()
    for event in app.stream(state):
        for _, payload in event.items():
            state.update(payload)
    return {"diagnosis": state.get("diagnosis", {}), "plan": state.get("plan", {})}
