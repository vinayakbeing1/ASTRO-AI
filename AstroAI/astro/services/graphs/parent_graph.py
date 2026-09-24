"""
G₂ Parent Chat Graph — Plan-and-Act over G₁ (A1–A7)

Flow:
- PLAN (LLM): emits subgoals + ordered actions (UseCache / Compute / Validate)
- REVIEW (LLM): critically verifies/patches the plan given prior slices
-  If changed, (1) invalidate A5→A7 cache, and (2) rewrite plan so A5→A7 use Compute.
- EXECUTE (code): runs actions, auto-computes prereqs, validates, may call REPLAN (LLM)
- FINALIZE (LLM): Finalizer composes the reply **using only slices materialized this turn**

No TTL/freshness — reuse is planner-driven. Q5 change = force recompute for A5→A7 via plan rewrite and cache purge.
"""

from __future__ import annotations
from typing import TypedDict, Any, Dict, List, Optional, Literal, Tuple, Set
import hashlib, json, re
from enum import Enum

import redis
from langgraph.graph import StateGraph, START, END
from django.contrib.auth.models import User
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from pydantic import BaseModel, Field

# ---- Import your G₁ helpers ----
from astro.services.graphs.question_graph import (
    WFState as G1State,
    get_kundli_from_user,
    run_g1_nodes_selective,
    G1_CANONICAL_ORDER,  # ["Q_INTENT","Q_A1",...,"Q_A7"]
)

# ---- LLM infra & prompts ----
from astro.services.llm import create_llm_chain
from astro.models import PromptTemplate

# =========================================================
# Redis Client
# =========================================================


def _make_redis_client() -> redis.Redis:
    url = getattr(settings, "REDIS_URL", None) or os.getenv(
        "REDIS_URL", "redis://localhost:6379/0"
    )
    return redis.Redis.from_url(url, decode_responses=True)


R = _make_redis_client()

# =========================================================
# Keys & helpers
# =========================================================

FOUNDATIONS_KEY = "astro:g2:{user_id}:foundations"
NODE_KEY = "astro:g2:{user_id}:node:{node_id}"
QA_LOG_KEY = "astro:g2:{user_id}:qa_log"


def _dumps(obj: dict) -> str:
    return json.dumps(obj, cls=DjangoJSONEncoder, separators=(",", ":"))


def _json_hash(payload: Any) -> str:
    return hashlib.sha256(_dumps(payload).encode("utf-8")).hexdigest()


def _rget_json(key: str) -> Optional[dict]:
    raw = R.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _rset_json(key: str, value: dict) -> None:
    R.set(key, _dumps(value))


def _rpush_json(key: str, value: dict) -> None:
    R.lpush(key, _dumps(value))


# =========================================================
# Node mapping (A1–A7 ONLY)
# =========================================================

OUTPUT_KEY_BY_NODE = {
    "Q_A1": "house_mapping",
    "Q_A2": "baseline_summary",
    "Q_A3": "house_deep_dive",
    "Q_A4": "varga_verification",
    "Q_A5": "dasha_alignment_result",
    "Q_A6": "transit_overlay_result",
    "Q_A7": "timing_summary",
}

ALIAS_BY_NODE = {
    "Q_A1": "a1",
    "Q_A2": "a2",
    "Q_A3": "a3",
    "Q_A4": "a4",
    "Q_A5": "a5",
    "Q_A6": "a6",
    "Q_A7": "a7",
}

A_NODES = list(OUTPUT_KEY_BY_NODE.keys())

A_PREREQS = {
    "Q_A1": [],
    "Q_A2": ["Q_A1"],
    "Q_A3": ["Q_A1"],
    "Q_A4": ["Q_A1", "Q_A2", "Q_A3"],
    "Q_A5": ["Q_A1", "Q_A3", "Q_A4"],
    "Q_A6": ["Q_A1", "Q_A3", "Q_A5"],
    "Q_A7": ["Q_A2", "Q_A4", "Q_A5", "Q_A6"],
}

# =========================================================
# IO helpers
# =========================================================


def _build_prior_outputs(user_id: int) -> Dict[str, Any]:
    prior = {alias: {} for alias in ALIAS_BY_NODE.values()}
    for node_id in A_NODES:
        snap = _rget_json(NODE_KEY.format(user_id=user_id, node_id=node_id))
        if not snap:
            continue
        out_key = OUTPUT_KEY_BY_NODE[node_id]
        alias = ALIAS_BY_NODE[node_id]
        prior[alias] = snap.get("payload", {}).get(out_key, {}) or {}
    return prior


def _sync_foundations(user: User) -> None:
    kundli = get_kundli_from_user(user)
    fkey = FOUNDATIONS_KEY.format(user_id=user.id)
    incoming = {
        "charts_hash": _json_hash(kundli.get("charts", {})),
        "metrics_hash": _json_hash(
            {
                "shadbala": kundli.get("shadbala"),
                "ashtaka_varga": kundli.get("ashtaka_varga"),
            }
        ),
        "dasha_hash": _json_hash({"vimsottari_dhasa": kundli.get("vimsottari_dhasa")}),
    }
    if (_rget_json(fkey) or {}) != incoming:
        _rset_json(fkey, incoming)


def _persist_node_snapshot(user_id: int, node_id: str, g1_state: G1State) -> None:
    out_key = OUTPUT_KEY_BY_NODE[node_id]
    payload = {out_key: g1_state.get(out_key, {})}
    snap = {"node_id": node_id, "dep_hash": _json_hash(payload), "payload": payload}
    _rset_json(NODE_KEY.format(user_id=user_id, node_id=node_id), snap)


def history_tail(
    chat_history: List[Dict[str, Any]], max_items: int = 10
) -> List[Dict[str, Any]]:
    return (chat_history or [])[-max_items:]


# =========================================================
# Models
# =========================================================


class Subgoal(BaseModel):
    id: str
    goal: str
    actions: List[List[str]]


class PlanSpec(BaseModel):
    subgoals: List[Subgoal] = Field(default_factory=list)
    notes: str = Field(default="")
    dasha_years: int = Field(default=5)


class Observations(BaseModel):
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    failure_reason: str = Field(default="")


class FinalReply(BaseModel):
    reply_text: str


# =========================================================
# LLM chains
# =========================================================


def planner_chain():
    prompt = PromptTemplate.objects.get(name="plan_act_planner_prompt")
    return create_llm_chain(
        parser=PlanSpec,
        prompt_template=prompt,
        metadata={"chain_type": "plan_act_planner"},
    )


def planner_replan_chain():
    prompt = PromptTemplate.objects.get(name="plan_act_replanner_prompt")
    return create_llm_chain(
        parser=PlanSpec,
        prompt_template=prompt,
        metadata={"chain_type": "plan_act_replanner"},
    )


def finalizer_chain():
    prompt = PromptTemplate.objects.get(name="finalizer_prompt")
    return create_llm_chain(
        parser=FinalReply, prompt_template=prompt, metadata={"chain_type": "finalizer"}
    )


# =========================================================
# Validation
# =========================================================


def _validate_predicate(
    name: str,
    slices: Dict[str, Any],
    trace: Optional[List[Dict[str, Any]]] = None,
    message: Optional[str] = None,
    plan: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    n = (name or "").strip().lower()
    a1, a2, a3, a4, a5, a6, a7 = (
        slices.get(k, {}) for k in ("a1", "a2", "a3", "a4", "a5", "a6", "a7")
    )
    nz = lambda x: isinstance(x, dict) and bool(x)
    has = lambda d, k: isinstance(d.get(k, None), list) and len(d.get(k, [])) > 0

    if n == "answer_sufficiency":
        return (
            nz(a1) and nz(a2) and nz(a3) and nz(a4),
            "insufficient_context_a1_to_a4_missing",
        )
    if n == "plan_consistency":
        viol = []
        if nz(a2) and not nz(a1):
            viol.append("a2_without_a1")
        if nz(a3) and not nz(a1):
            viol.append("a3_without_a1")
        if nz(a4) and not (nz(a1) and nz(a2) and nz(a3)):
            viol.append("a4_missing_prereqs")
        if nz(a5) and not (nz(a1) and nz(a3) and nz(a4)):
            viol.append("a5_missing_prereqs")
        if nz(a6) and not (nz(a1) and nz(a3) and nz(a5)):
            viol.append("a6_missing_prereqs")
        if nz(a7) and not (nz(a2) and nz(a4) and nz(a5) and nz(a6)):
            viol.append("a7_missing_prereqs")
        return (
            len(viol) == 0,
            "" if not viol else "inconsistent_dependencies:" + ",".join(viol),
        )
    if n == "scope_alignment":
        return (
            any(nz(s) for s in (a1, a2, a3, a4, a5, a6, a7)),
            "no_material_slices_present",
        )
    if n == "evidence_alignment":
        using_downstream = nz(a5) or nz(a6) or nz(a7)
        ctx_ok = nz(a1) and nz(a3) and nz(a4)
        return (not using_downstream or ctx_ok, "downstream_used_without_a1_a3_a4")
    if n == "contradictions_check":
        viol = []
        baseline = (a2.get("baseline_grade") or "").strip().lower()
        varga = (a4.get("varga_confirmation") or "").strip().lower()
        if baseline == "strong" and varga == "contradictory":
            viol.append("strong_baseline_vs_contradictory_varga")
        if baseline == "weak" and varga == "supportive":
            viol.append("weak_baseline_vs_supportive_varga")
        fav = a5.get("favorable_periods", []) if isinstance(a5, dict) else []
        if (
            isinstance(fav, list)
            and len(fav) > 0
            and (a7.get("confidence") or "") == "Low"
        ):
            viol.append("favorable_dasha_with_low_timing_confidence")
        return (len(viol) == 0, "" if not viol else "contradictions:" + ",".join(viol))
    if n == "risk_balance":
        threats = []
        if isinstance(a3, dict):
            if isinstance(a3.get("threats"), list):
                threats = a3["threats"]
            elif isinstance(a3.get("house_evaluation"), list):
                for h in a3["house_evaluation"]:
                    if isinstance(h, dict) and isinstance(h.get("threats"), list):
                        threats.extend(h["threats"])
        return (len(threats) == 0) or nz(a3), "" if (
            len(threats) == 0 or nz(a3)
        ) else "risks_detected_but_nowhere_to_surface"
    if n == "cache_usefulness":
        present = sum(1 for s in (a1, a2, a3, a4, a5, a6, a7) if nz(s))
        return (present >= 2, "cache_not_useful_minimal_material_found")
    if n == "context_ready":
        return (nz(a1) and nz(a2) and nz(a3) and nz(a4), "context_not_ready")
    if n == "timing_ready":
        return (
            has(a7, "windows") and (a7.get("confidence") in {"High", "Medium", "Low"}),
            "timing_not_ready",
        )
    return True, ""


# =========================================================
# Action parser
# =========================================================

ACTION_RE = re.compile(
    r"^\s*(?:(?P<kind>UseCache|Compute|Validate)(?:\s*(?:\(|:|-)?\s*(?P<arg>[A-Za-z0-9_ ]+)\)?)?)\s*$",
    re.IGNORECASE,
)

_NODE_CANON = {
    "A1": "Q_A1",
    "A2": "Q_A2",
    "A3": "Q_A3",
    "A4": "Q_A4",
    "A5": "Q_A5",
    "A6": "Q_A6",
    "A7": "Q_A7",
}
_VALIDATORS = {
    "answer_sufficiency",
    "plan_consistency",
    "scope_alignment",
    "evidence_alignment",
    "contradictions_check",
    "risk_balance",
    "cache_usefulness",
    "context_ready",
    "timing_ready",
}


def _normalize_node_id(raw: str) -> str:
    raw = raw.strip()
    if raw in _NODE_CANON:
        return _NODE_CANON[raw]
    if raw.startswith("Q_") and raw in _NODE_CANON.values():
        return raw
    raise ValueError(f"Unknown node id: {raw}")


def _parse_action(action_str: str) -> Tuple[str, Optional[str]]:
    if not isinstance(action_str, str):
        raise ValueError(f"Action must be str, got {type(action_str)}")
    m = ACTION_RE.match(action_str)
    if not m:
        raise ValueError(f"Bad action syntax: {action_str}")
    kind = {"usecache": "UseCache", "compute": "Compute", "validate": "Validate"}[
        m.group("kind").lower()
    ]
    raw_arg = (m.group("arg") or "").strip()
    if kind in ("UseCache", "Compute"):
        if not raw_arg:
            raise ValueError(f"Missing node id for {kind}.")
        return kind, _normalize_node_id(raw_arg)
    if kind == "Validate":
        if not raw_arg:
            raise ValueError("Missing validator name for Validate.")
        name = raw_arg.lower().replace(" ", "_")
        if name not in _VALIDATORS:
            raise ValueError(f"Unknown validator: {raw_arg}")
        return "Validate", name
    raise ValueError(f"Unknown action kind: {kind}")


# =========================================================
# G₂ Nodes (Plan → Review → Execute → Finalize)
# =========================================================


class ChatTurn(TypedDict, total=False):
    message: str
    user: User
    chat_history: List[Dict[str, Any]]
    preferences: Dict[str, Any]


class G2State(TypedDict, total=False):
    turn: ChatTurn
    plan: PlanSpec
    observations: Observations
    chat_reply: str
    errors: List[str]
    _g1_state: Dict[str, Any]
    _materialized_nodes: List[str]
    dasha_years: int


def g2_ingest(state: G2State) -> G2State:
    state.setdefault("errors", [])
    state["_materialized_nodes"] = []
    return state


def g2_plan(state: G2State) -> G2State:
    user: User = state["turn"]["user"]
    _sync_foundations(user)
    state["plan"] = planner_chain().invoke(
        {
            "history": history_tail(state["turn"].get("chat_history", [])),
            "message": state["turn"]["message"],
            "prior_outputs": _build_prior_outputs(user.id),
        }
    )
    state["dasha_years"] = state["plan"].dasha_years
    state["observations"] = Observations(trace=[], failure_reason="")
    return state


def g2_review(state: G2State) -> G2State:
    user: User = state["turn"]["user"]
    state["plan"] = planner_replan_chain().invoke(
        {
            "history": history_tail(state["turn"].get("chat_history", [])),
            "message": state["turn"]["message"],
            "prior_outputs": _build_prior_outputs(user.id),
            "last_plan": state["plan"].model_dump(),
            "observations": {"trace": [], "failure_reason": ""},
            "mode": "pre_exec",
        }
    )
    return state


def _merge_slices_from_state(g1_state: G1State) -> Dict[str, Any]:
    return {
        "a1": g1_state.get("house_mapping", {}),
        "a2": g1_state.get("baseline_summary", {}),
        "a3": g1_state.get("house_deep_dive", {}),
        "a4": g1_state.get("varga_verification", {}),
        "a5": g1_state.get("dasha_alignment_result", {}),
        "a6": g1_state.get("transit_overlay_result", {}),
        "a7": g1_state.get("timing_summary", {}),
    }


def g2_execute(state: G2State) -> G2State:
    """Run actions from the (possibly rewritten) plan."""
    user: User = state["turn"]["user"]
    kundli = get_kundli_from_user(user)

    # Start clean; only explicit UseCache actions will load prior slices.
    g1_state: G1State = {"question": state["turn"]["message"], "kundli": kundli}

    g1_state["dasha_years"] = state["dasha_years"]

    trace: List[Dict[str, Any]] = []
    materialized: Set[str] = set()

    def record(action: str, success: bool, info: Dict[str, Any] | None = None):
        trace.append({"action": action, "success": success, "info": info or {}})

    def _ensure_prereqs_then_compute(ai: str):
        for p in A_PREREQS.get(ai, []):
            out_key = OUTPUT_KEY_BY_NODE[p]
            if not g1_state.get(out_key):
                snap = _rget_json(NODE_KEY.format(user_id=user.id, node_id=p))
                if snap:
                    g1_state.update(snap.get("payload", {}))
                    materialized.add(p)
                    record(f"UseCache({p})", True, {"autopatch": True})
                else:
                    gs = run_g1_nodes_selective(g1_state, [p])
                    g1_state.update(gs)
                    _persist_node_snapshot(user.id, p, g1_state)
                    materialized.add(p)
                    record(f"Compute({p})", True, {"autopatch": True})
        gs = run_g1_nodes_selective(g1_state, [ai])
        g1_state.update(gs)
        _persist_node_snapshot(user.id, ai, g1_state)
        materialized.add(ai)
        record(f"Compute({ai})", True, {})

    # Execute
    sg_index = 0
    while sg_index < len(state["plan"].subgoals):
        sg = state["plan"].subgoals[sg_index]
        for inner in sg.actions:
            action_str = inner[0]
            kind, arg = _parse_action(action_str)

            if kind == "UseCache":
                node_id = arg
                snap = _rget_json(NODE_KEY.format(user_id=user.id, node_id=node_id))
                if snap:
                    g1_state.update(snap.get("payload", {}))
                    materialized.add(node_id)
                    record(action_str, True, {"used": True})
                else:
                    record(action_str, True, {"used": False})

            elif kind == "Compute":
                node_id = arg
                if node_id not in A_NODES:
                    record(action_str, False, {"error": "invalid_node"})
                    new_plan = planner_replan_chain().invoke(
                        {
                            "history": history_tail(
                                state["turn"].get("chat_history", [])
                            ),
                            "message": state["turn"]["message"],
                            "prior_outputs": _build_prior_outputs(user.id),
                            "last_plan": state["plan"].model_dump(),
                            "observations": {
                                "trace": trace,
                                "failure_reason": "invalid_node",
                            },
                            "mode": "on_fail",
                        }
                    )
                    state["plan"] = new_plan
                    sg_index = 0
                    break
                _ensure_prereqs_then_compute(node_id)

            elif kind == "Validate":
                ok, reason = _validate_predicate(
                    arg, _merge_slices_from_state(g1_state)
                )
                record(action_str, ok, {"reason": reason})
                if not ok:
                    new_plan = planner_replan_chain().invoke(
                        {
                            "history": history_tail(
                                state["turn"].get("chat_history", [])
                            ),
                            "message": state["turn"]["message"],
                            "prior_outputs": _build_prior_outputs(user.id),
                            "last_plan": state["plan"].model_dump(),
                            "observations": {"trace": trace, "failure_reason": reason},
                            "mode": "on_fail",
                        }
                    )
                    state["plan"] = new_plan
                    sg_index = 0
                    break
        else:
            sg_index += 1
            continue
        continue

    state["_g1_state"] = g1_state
    state["_materialized_nodes"] = sorted(materialized)
    state["observations"] = Observations(trace=trace, failure_reason="")
    return state


def _filter_slices_to_materialized(
    slices: Dict[str, Any], mat_nodes: List[str]
) -> Dict[str, Any]:
    """Keep only aliases for nodes materialized this turn; blank others."""
    normalized = []
    for n in mat_nodes or []:
        if n.startswith("Q_"):
            normalized.append(n)
        elif n in _NODE_CANON:
            normalized.append(_NODE_CANON[n])
    keep_aliases = {ALIAS_BY_NODE[qid] for qid in normalized if qid in ALIAS_BY_NODE}
    out = {}
    for alias in ("a1", "a2", "a3", "a4", "a5", "a6", "a7"):
        out[alias] = (
            slices.get(alias)
            if (alias in keep_aliases and isinstance(slices.get(alias), dict))
            else {}
        )
    return out


def g2_finalize(state: G2State) -> G2State:
    """Finalizer LLM composes the chat reply using ONLY slices built/used this turn."""
    g1_state = state.get("_g1_state", {}) or {}
    slices_all = _merge_slices_from_state(g1_state)
    slices_now = _filter_slices_to_materialized(
        slices_all, state.get("_materialized_nodes", [])
    )

    result = finalizer_chain().invoke(
        {
            "history": history_tail(state["turn"].get("chat_history", [])),
            "message": state["turn"]["message"],
            "slices": slices_now,
        }
    )
    state["chat_reply"] = (
        result.reply_text
        if getattr(result, "reply_text", None)
        else "I couldn’t compose a complete reply from the current data."
    )

    # Log
    user: User = state["turn"]["user"]
    _rpush_json(
        QA_LOG_KEY.format(user_id=user.id),
        {
            "message": state["turn"]["message"],
            "plan": state.get("plan").model_dump() if state.get("plan") else {},
            "observations": state.get("observations").model_dump()
            if state.get("observations")
            else {},
            "materialized_nodes": state.get("_materialized_nodes", []),
            "reply": state["chat_reply"],
        },
    )
    state.pop("_g1_state", None)
    return state


# =========================================================
# Build & Run
# =========================================================


def build_parent_chat_graph():
    g = StateGraph(G2State)
    g.add_node("INGEST", g2_ingest)
    g.add_node("PLAN", g2_plan)
    g.add_node("REVIEW", g2_review)
    g.add_node("EXECUTE", g2_execute)
    g.add_node("FINALIZE", g2_finalize)
    g.add_edge(START, "INGEST")
    g.add_edge("INGEST", "PLAN")
    g.add_edge("PLAN", "REVIEW")
    g.add_edge("REVIEW", "EXECUTE")
    g.add_edge("EXECUTE", "FINALIZE")
    g.add_edge("FINALIZE", END)
    return g.compile()


# Optional: LC Postgres history
from astro.services.chat_history_store import get_lc_history, _to_chat_turns


def run_chat_turn(
    message: str,
    user: User,
    preferences: Optional[Dict[str, Any]] = None,
    history_tail_n: int = 20,
) -> str:
    """
    Message → PLAN (LLM) → REVIEW (LLM) → EXECUTE (code) → FINALIZE (LLM).
    Persists user/assistant turns to Postgres if available.
    """
    lc_hist = get_lc_history(user)
    prior_turns = _to_chat_turns(lc_hist.messages, max_items=history_tail_n)

    app = build_parent_chat_graph()
    state: G2State = {
        "turn": {
            "message": message,
            "user": user,
            "chat_history": prior_turns,
            "preferences": preferences or {},
        }
    }

    for event in app.stream(state):
        for _, payload in event.items():
            state.update(payload)

    reply = state.get("chat_reply", "")
    try:
        lc_hist.add_user_message(message)
        if reply:
            lc_hist.add_ai_message(reply)
    except Exception:
        pass
    return reply
