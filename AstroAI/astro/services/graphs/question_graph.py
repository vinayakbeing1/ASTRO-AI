"""
LangGraph assembly for AstroAI: orchestrates the end-to-end workflow
using chains and tools.

Public API: build_graph() and run_graph(question, birthdata).
"""
from __future__ import annotations
from typing import TypedDict, Any, Dict, Optional, List
from langgraph.graph import StateGraph, START, END
from astro.services.parsers.question_parsers import (
    HouseMapping,
    BaselineSummary,
    DeepDiveEvaluation,
    DivisionalChartVerification,
    DashaAlignment,
    TransitOverlay,
    TimingWindows,
    SynthesisOutput,
    Q5RefineOut,
)
from jhora.panchanga import drik
from astro.models import PromptTemplate
from utils.select_dasha import filter_dasha_by_horizon

from astro.services.llm import create_llm_chain
from astro.services.astrology.astro import get_current_transit_data
from astro.services.astrology.transit_chart import tajaka_chart_for_date
from django.contrib.auth.models import User

Q_A1 = "Q_A1"
Q_A2 = "Q_A2"
Q_A3 = "Q_A3"
Q_A4 = "Q_A4"
Q_A5 = "Q_A5"
Q_A6 = "Q_A6"
Q_A7 = "Q_A7"
Q_A8 = "Q_A8"


class WFState(TypedDict, total=False):
    # Inputs
    question: Optional[str]
    kundli: Dict[str, Any]
    transit_now: Dict[str, Any]
    house_mapping: Dict[str, Any]
    baseline_summary: Dict[str, Any]
    house_deep_dive: Dict[str, Any]
    divisional_charts: List[str]
    varga_verification: Dict[str, Any]
    dasha_years: int
    dasha_alignment_result: Dict[str, Any]
    transit_overlay_result: Dict[str, Any]
    timing_summary: Dict[str, Any]
    final_synthesis: Dict[str, Any]


def get_kundli_from_user(user: User) -> Dict[str, Any]:
    """Fetch and structure the user's kundli data for graph input."""
    return {
        "shadbala": user.charts.shadbala,
        "ashtaka_varga": user.charts.ashtaka_varga,
        "vimsottari_dhasa": user.charts.vimsottari_dhasa,
        "charts": user.charts.charts,
        "birthdata": user.profile.get_birthdata(),
    }


def q_a1_house_mapping(state: WFState) -> WFState:
    """Map question to houses and key planets."""
    kundli = state["kundli"]

    house_mapping_chain = create_llm_chain(
        parser=HouseMapping,
        prompt_template=PromptTemplate.objects.get(
            name="question_house_mapping_prompt"
        ),
        metadata={"user": state.get("user"), "chain_type": "question_house_mapping"},
    )

    res = house_mapping_chain.invoke(
        {"question": state.get("question"), "d1_chart": kundli["charts"]["D1"]}
    )
    return {"house_mapping": res.model_dump()}


def q_a2_baseline(state: WFState) -> WFState:
    """Baseline summary of the natal chart."""
    kundli = state["kundli"]
    baseline_summary_chain = create_llm_chain(
        parser=BaselineSummary,
        prompt_template=PromptTemplate.objects.get(
            name="question_baseline_summary_prompt"
        ),
        metadata={"user": state.get("user"), "chain_type": "question_baseline_summary"},
    )
    res = baseline_summary_chain.invoke(
        {
            "who_matters": state["house_mapping"]["who_matters"],
            "d1_chart": kundli["charts"]["D1"],
            "shadbala": kundli["shadbala"],
        }
    )
    return {"baseline_summary": res.model_dump()}


def q_a3_deep_dive(state: WFState) -> WFState:
    """In-depth house and planet condition analysis."""
    kundli = state["kundli"]
    deep_dive_chain = create_llm_chain(
        parser=DeepDiveEvaluation,
        prompt_template=PromptTemplate.objects.get(name="question_deep_dive_prompt"),
        metadata={"user": state.get("user"), "chain_type": "question_deep_dive"},
    )
    res = deep_dive_chain.invoke(
        {
            "a1_output": state["house_mapping"],
            "d1_chart": kundli["charts"]["D1"],
            "ashtakavarga": kundli["ashtaka_varga"],
        }
    )
    return {"house_deep_dive": res.model_dump()}


def q_a4_varga(state: WFState) -> WFState:
    """Verify divisional chart support for key houses."""
    kundli = state["kundli"]
    divisional = state.get("divisional_charts", {})
    relevant = {c: kundli["charts"][c] for c in divisional if c in kundli["charts"]}

    divisional_chart_chain = create_llm_chain(
        parser=DivisionalChartVerification,
        prompt_template=PromptTemplate.objects.get(
            name="question_divisional_chart_prompt"
        ),
        metadata={"user": state.get("user"), "chain_type": "question_divisional_chart"},
    )
    res = divisional_chart_chain.invoke(
        {
            "a1_output": state["house_mapping"],
            "a2_output": state["baseline_summary"],
            "a3_output": state["house_deep_dive"],
            "divisional_charts": relevant,
        }
    )
    return {"varga_verification": res.model_dump()}


from datetime import date
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Optional, Literal, Tuple

# -- Chain factory --


def q5_window_refiner_chain():
    return create_llm_chain(
        parser=Q5RefineOut,
        prompt_template=PromptTemplate.objects.get(name="q5_window_refiner_prompt"),
        metadata={"chain_type": "q5_window_refiner"},
    )

# ------------------------
# Q_A5 main (Step 2 refine, then align) — with adaptive window widening
# ------------------------


def q_a5_dasha(state: WFState) -> WFState:
    """
    Narrow the preselected dasha layer/horizon via the Refiner, optionally widen the window
    (keeping the same layer) if results are sparse/low-confidence, then run Q_A5 alignment
    on the clipped dasha table.

    Preconditions set by Step 1:
      state["dasha_layer"] in {"MD","AD","PD","SD"}
      state["horizon"] = {"unit": "...", "value": int}  # dict or object
    Requires (from earlier slices): house_mapping (A1), house_deep_dive (A3), varga_verification (A4)
    """
    kundli = state["kundli"]

    # fallback when refiner found no specific windows
    final_table = filter_dasha_by_horizon(
        kundli["vimsottari_dhasa"],
        layers=["MD", "AD", "PD", "SD"],
        horizon="years",
        thresholds={"unit": "years", "value": state.get("dasha_years", 5)},
    )

    # ---- 4) Run Q_A5 alignment LLM on the pruned table
    dasha_alignment_chain = create_llm_chain(
        parser=DashaAlignment,
        prompt_template=PromptTemplate.objects.get(
            name="question_dasha_alignment_prompt"
        ),
        metadata={"user": state.get("user"), "chain_type": "question_dasha_alignment"},
    )
    res = dasha_alignment_chain.invoke(
        {
            "a1_output": state["house_mapping"],
            "a3_output": state["house_deep_dive"],
            "dasha_table": final_table,  # normalized compact rows at selected layer
            "a4_output": state["varga_verification"],
        }
    )

    # ---- 5) Persist Q_A5 result + choices for downstream Q_A6/Q_A7
    return {"dasha_alignment_result": res.model_dump()}


def q_a6_transits(state: WFState) -> WFState:
    """Overlay current transits on natal chart and analyze effects."""
    birth = state["kundli"]["birthdata"]
    place = drik.Place(
        birth["POB"]["name"],
        birth["POB"]["lat"],
        birth["POB"]["lon"],
        birth["POB"]["timezone"],
    )

    transit = get_current_transit_data(place)

    transit_overlay_chain = create_llm_chain(
        parser=TransitOverlay,
        prompt_template=PromptTemplate.objects.get(name="question_transit_prompt"),
        metadata={"user": state.get("user"), "chain_type": "question_transit"},
    )
    res = transit_overlay_chain.invoke(
        {
            "transit": transit,
            "a1_output": state["house_mapping"],
            "a3_output": state["house_deep_dive"],
            "a5_output": state["dasha_alignment_result"],
        }
    )
    return {"transit_overlay_result": res.model_dump()}


def q_a7_timing(state: WFState) -> WFState:
    """Summarize timing insights from dashas and transits."""
    timing_chain = create_llm_chain(
        parser=TimingWindows,
        prompt_template=PromptTemplate.objects.get(name="question_timing_prompt"),
        metadata={"user": state.get("user"), "chain_type": "question_timing"},
    )

    res = timing_chain.invoke(
        {
            "a2_output": state["baseline_summary"],
            "a4_output": state["varga_verification"],
            "a5_output": state["dasha_alignment_result"],
            "a6_output": state["transit_overlay_result"],
        }
    )
    return {"timing_summary": res.model_dump()}


def q_a8_synthesis(state: WFState) -> WFState:
    """Final synthesis integrating all prior analyses."""

    final_synthesis_chain = create_llm_chain(
        parser=SynthesisOutput,
        prompt_template=PromptTemplate.objects.get(
            name="question_final_synthesis_prompt"
        ),
        metadata={"user": state.get("user"), "chain_type": "question_final_synthesis"},
    )
    res = final_synthesis_chain.invoke(
        {
            "question": state.get("method_decision", {}).get(
                "client_question", state.get("question", "")
            ),
            "a1_output": state["house_mapping"],
            "a2_output": state["baseline_summary"],
            "a3_output": state["house_deep_dive"],
            "a4_output": state["varga_verification"]
            if "varga_verification" in state
            else {},
            "a5_output": state["dasha_alignment_result"]
            if "dasha_alignment_result" in state
            else {},
            "a6_output": state["transit_overlay_result"]
            if "transit_overlay_result" in state
            else {},
            "a7_output": state["timing_summary"] if "timing_summary" in state else {},
        }
    )
    return {"final_synthesis": res.model_dump()}


def build_question_graph():
    """Assemble the QUESTION workflow graph with strict gating so Q_A7 runs last."""
    g = StateGraph(WFState)

    g.add_node(Q_A1, q_a1_house_mapping)
    g.add_node(Q_A2, q_a2_baseline)
    g.add_node(Q_A3, q_a3_deep_dive)
    g.add_node(Q_A4, q_a4_varga)
    g.add_node(Q_A5, q_a5_dasha)
    g.add_node(Q_A6, q_a6_transits)
    g.add_node(Q_A7, q_a7_timing)
    g.add_node(Q_A8, q_a8_synthesis)

    g.add_edge(START, Q_A1)
    g.add_edge(Q_A1, Q_A2)
    g.add_edge(Q_A1, Q_A3)

    g.add_edge(Q_A3, Q_A4)
    g.add_edge(Q_A4, Q_A5)
    g.add_edge(Q_A5, Q_A6)
    g.add_edge(Q_A6, Q_A7)
    g.add_edge(Q_A7, Q_A8)
    g.add_edge(Q_A8, END)

    return g.compile()


# ====== G₁: Selective execution helpers & node registry ======

# Node registry so G₂ can call nodes individually when needed
G1_NODE_REGISTRY = {
    "Q_A1": q_a1_house_mapping,
    "Q_A2": q_a2_baseline,
    "Q_A3": q_a3_deep_dive,
    "Q_A4": q_a4_varga,
    "Q_A5": q_a5_dasha,
    "Q_A6": q_a6_transits,
    "Q_A7": q_a7_timing,
    "Q_A8": q_a8_synthesis,
}

# Dependency map for selective recompute (used by G₂ planner)
G1_DEPENDENCIES = {
    "Q_A1": [],
    "Q_A2": ["Q_A1"],
    "Q_A3": ["Q_A1"],
    "Q_A4": ["Q_A3"],  # assumes Q_A2 is read by Q_A4 (state access)
    "Q_A5": ["Q_A4"],
    "Q_A6": ["Q_A5"],
    "Q_A7": ["Q_A6"],
    "Q_A8": ["Q_A7"],
}

# A compact list showing the canonical order (useful for topological sort)
G1_CANONICAL_ORDER = [
    "Q_A1",
    "Q_A2",
    "Q_A3",
    "Q_A4",
    "Q_A5",
    "Q_A6",
    "Q_A7",
]


def run_g1_nodes_selective(
    initial_state: WFState,
    nodes_to_run: list[str],
) -> WFState:
    """
    Execute only the requested G₁ nodes (in topological order), assuming
    that any needed prior states are already injected into `initial_state`.
    Returns the updated WFState after executing those nodes.
    """
    state = dict(initial_state)

    # execute in canonical order, but only for nodes requested
    for node_id in G1_CANONICAL_ORDER:
        if node_id in nodes_to_run:
            fn = G1_NODE_REGISTRY[node_id]
            out = fn(state)
            state.update(out)
    return state
