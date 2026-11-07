"""The investigator team: a LangGraph StateGraph over one gauge.

    triage ──Trusted──────────────────────────────────────────▶ narrator
       └─Watch/Stale─▶ evidence_collector ─▶ hypothesis_ranker ─▶ skeptic ─accept─▶ narrator
                                                   ▲               │
                                                   └──object (≤2)──┘

triage            no LLM: reads the M1 Report (band, score, residual, top shift, M1 cause).
evidence_collector no LLM: runs the four tools in tools.py.
hypothesis_ranker LLM (or fallback): ranked causes, always incl. datum_change and inconclusive.
skeptic           LLM on a different family (or fallback): accept, or a typed objection.
                  A third objection does not loop again; it goes to the narrator as unresolved.
narrator          LLM (or fallback): <= 120 words for a utility manager.

Any LLM failure (exception, unparsable output, a guard below) falls back to the deterministic
node for that step; the trace payload records it. The loop count lives in the state, so no
model output can make the graph loop forever.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
from langgraph.graph import END, START, StateGraph

from driftwatch.agents import fallbacks, llm, tools
from driftwatch.agents.models import (
    CAUSE_KEYS,
    REQUIRED_CAUSES,
    Hypothesis,
    Narration,
    Ranking,
    SkepticVerdict,
)
from driftwatch.agents.trace import TraceRecorder
from driftwatch.modules.rating_curve import report as rc_report

MAX_LOOPS = 2  # skeptic objections that send the ranker round again
MAX_WORDS = 120


class AgentState(TypedDict, total=False):
    site: str
    llm: str
    facts: dict[str, Any]  # triage + evidence, what the LLM nodes see
    ranking: dict[str, Any]
    rankings: list[dict[str, Any]]
    objections: list[dict[str, Any]]
    verdict: dict[str, Any]
    final: dict[str, Any] | None
    narration: str
    usage: list[dict[str, Any]]


def _dump(x: Any) -> str:
    return json.dumps(x, indent=1, default=str)


# --------------------------------------------------------------------------- deterministic nodes


def triage_facts(site: str) -> dict[str, Any]:
    rep = tools.report(site)
    ds = tools.dataset(site)
    as_of = ds.fetched_at
    inputs = rc_report.trust_inputs(ds, rep.relationship, rep.drift, as_of)
    med = float(np.median(inputs.recent_residual_pct)) if inputs.recent_residual_pct else 0.0
    top = rc_report.top_shift(rep.relationship.reference_end, rep.drift)
    return {
        "site": site,
        "site_name": rep.site_name,
        "band": rep.trust.band,
        "score": round(rep.trust.score, 1),
        "score_display": f"Trust score {rep.trust.score:.0f}/100 ({rep.trust.band}).",
        "deductions": [d.model_dump() for d in rep.trust.deductions],
        "recent_median_residual_pct": round(med, 1),
        "normal_scatter_pct": round(inputs.normal_scatter_pct, 1),
        "direction": "positive" if med > 0 else "negative",
        "recent_rated": list(inputs.recent_rated),
        "top_shift": top.model_dump(mode="json") if top else None,
        "reference_window": [
            str(rep.relationship.reference_start),
            str(rep.relationship.reference_end),
        ],
        "m1_cause": rep.likely_cause,
        "m1_why": rep.narrative,
    }


def collect_evidence(site: str, triage: dict[str, Any]) -> dict[str, Any]:
    split = triage["top_shift"]["time"] if triage["top_shift"] else None
    return {
        "channel_geometry": tools.channel_geometry_trend(site, split),
        "field_notes": tools.field_notes(site),
        "flood_context": tools.flood_context(site, split),
        "site_metadata": tools.site_metadata(site),
    }


# --------------------------------------------------------------------------- guards on LLM output


def clean_ranking(r: Ranking, facts: dict[str, Any], objections: list[dict]) -> Ranking:
    """Catalog keys only, no duplicates, sign_matches recomputed from the catalog,
    datum_change + inconclusive always present, sorted by confidence."""
    direction = facts["triage"]["direction"]
    seen: dict[str, Hypothesis] = {}
    for h in r.hypotheses:
        if h.cause in CAUSE_KEYS and h.cause not in seen:
            seen[h.cause] = h.model_copy(
                update={"sign_matches": fallbacks._sign_ok(h.cause, direction)}
            )
    if REQUIRED_CAUSES[0] not in seen or REQUIRED_CAUSES[1] not in seen:
        fb = {h.cause: h for h in fallbacks.rank(facts, objections).hypotheses}
        for k in REQUIRED_CAUSES:
            seen.setdefault(k, fb[k])
    hyps = sorted(seen.values(), key=lambda h: -h.confidence)
    return Ranking(hypotheses=hyps, reasoning=r.reasoning)


def narration_ok(text: str, facts: dict[str, Any]) -> str | None:
    """None if fine, else why it was rejected."""
    n = len(text.split())
    if n > MAX_WORDS:
        return f"{n} words > {MAX_WORDS}"
    s = facts["triage"]["score"]
    if not re.search(rf"\b({round(s)}|{s:.1f})\b", text):
        return "the trust score is missing"
    return None


# --------------------------------------------------------------------------- graph


def build_graph(rec: TraceRecorder):
    """Compile the StateGraph. `rec` receives every node's TraceEvents."""

    async def triage(state: AgentState) -> AgentState:
        rec.emit("triage", "started", {})
        t = triage_facts(state["site"])
        route = "narrator" if t["band"] == "Trusted" else "evidence_collector"
        rec.emit("triage", "completed", {**t, "route": route})
        return {
            "facts": {"triage": t},
            "objections": [],
            "rankings": [],
            "usage": [],
            "final": None,
        }

    async def evidence_collector(state: AgentState) -> AgentState:
        rec.emit("evidence_collector", "started", {})
        ev = collect_evidence(state["site"], state["facts"]["triage"])
        for name, out in ev.items():
            rec.emit("evidence_collector", "progress", {"tool": name, "result": out})
        sig = fallbacks.channel_signature(ev["channel_geometry"])
        rec.emit("evidence_collector", "completed", {"tools": list(ev), "channel_signature": sig})
        return {"facts": {**state["facts"], **ev}}

    async def hypothesis_ranker(state: AgentState) -> AgentState:
        facts, objs = state["facts"], state["objections"]
        rnd = len(state["rankings"]) + 1
        rec.emit("hypothesis_ranker", "started", {"round": rnd, "objections_so_far": len(objs)})
        meta: dict[str, Any] = {"model": "fallback"}
        if llm.backend("ranker", state["llm"]) is None:
            r = fallbacks.rank(facts, objs)
        else:
            try:
                r, meta = await llm.structured(
                    "ranker",
                    state["llm"],
                    Ranking,
                    llm.prompt("ranker"),
                    llm.prompt(
                        "ranker_input", facts=_dump(_ranker_view(facts)), objections=_dump(objs)
                    ),
                )
                r = clean_ranking(r, facts, objs)
            except Exception as e:  # noqa: BLE001 - any model failure -> rules
                meta = {"model": "fallback", "llm_error": f"{type(e).__name__}: {e}"[:300]}
                r = fallbacks.rank(facts, objs)
        out = r.model_dump()
        rec.emit("hypothesis_ranker", "completed", {"round": rnd, **out, **meta})
        return {
            "ranking": out,
            "rankings": [*state["rankings"], out],
            "usage": [*state["usage"], {"node": "hypothesis_ranker", **meta}],
        }

    async def skeptic(state: AgentState) -> AgentState:
        facts = state["facts"]
        ranking = Ranking.model_validate(state["ranking"])
        rec.emit("skeptic", "started", {"reviewing": ranking.top.cause})
        meta: dict[str, Any] = {"model": "fallback"}
        rules = fallbacks.critique(facts, ranking)
        if llm.backend("skeptic", state["llm"]) is None:
            v = rules
        else:
            try:
                v, meta = await llm.structured(
                    "skeptic",
                    state["llm"],
                    SkepticVerdict,
                    llm.prompt("skeptic"),
                    llm.prompt(
                        "skeptic_input",
                        facts=_dump(_ranker_view(facts)),
                        channel=_dump(facts.get("channel_geometry")),
                        ranking=_dump(ranking.model_dump()),
                        signature=fallbacks.channel_signature(facts.get("channel_geometry")),
                        objections=_dump(state["objections"]),
                    ),
                )
                # hard guard: a sign contradiction is never accepted
                if v.verdict == "accept" and rules.objection == "sign_mismatch":
                    meta["guard"] = "sign_mismatch overrides the model's accept"
                    v = rules
                # the sign check is arithmetic, not opinion: relabel a wrong 'sign_mismatch'
                elif v.objection == "sign_mismatch" and ranking.top.sign_matches:
                    meta["guard"] = "objection relabelled: the top cause's sign does match"
                    v = v.model_copy(update={"objection": "other"})
            except Exception as e:  # noqa: BLE001
                meta = {"model": "fallback", "llm_error": f"{type(e).__name__}: {e}"[:300]}
                v = rules
        out = {
            **v.model_dump(),
            "objected_cause": ranking.top.cause if v.verdict == "object" else None,
        }
        objs = state["objections"] + ([out] if v.verdict == "object" else [])
        loop = v.verdict == "object" and len(objs) <= MAX_LOOPS
        rec.emit(
            "skeptic", "completed", {**out, **meta, "loop_back": loop, "objections": len(objs)}
        )
        return {
            "verdict": out,
            "objections": objs,
            "usage": [*state["usage"], {"node": "skeptic", **meta}],
        }

    async def narrator(state: AgentState) -> AgentState:
        facts = state["facts"]
        rec.emit("narrator", "started", {})
        final = None
        if state.get("ranking"):
            r = Ranking.model_validate(state["ranking"])
            verdict = state.get("verdict") or {}
            final = {
                "cause": r.top.cause,
                "confidence": r.top.confidence,
                "first_cause": state["rankings"][0]["hypotheses"][0]["cause"],
                "objections": len(state["objections"]),
                "unresolved": verdict.get("verdict") == "object",
                "skeptic_argument": verdict.get("argument"),
            }
        meta: dict[str, Any] = {"model": "fallback"}
        text = fallbacks.narrate(facts, final).text
        if llm.backend("narrator", state["llm"]) is not None:
            try:
                n, meta = await llm.structured(
                    "narrator",
                    state["llm"],
                    Narration,
                    llm.prompt("narrator"),
                    llm.prompt("narrator_input", facts=_dump(facts["triage"]), final=_dump(final)),
                )
                bad = narration_ok(n.text, facts)
                if bad:
                    meta["rejected"] = bad
                    meta["rejected_text"] = n.text
                else:
                    text = n.text.strip()
            except Exception as e:  # noqa: BLE001
                meta = {"model": "fallback", "llm_error": f"{type(e).__name__}: {e}"[:300]}
        rec.emit("narrator", "completed", {"narration": text, "final": final, **meta})
        return {
            "narration": text,
            "final": final,
            "usage": [*state["usage"], {"node": "narrator", **meta}],
        }

    def after_triage(state: AgentState) -> str:
        return "narrator" if state["facts"]["triage"]["band"] == "Trusted" else "evidence_collector"

    def after_skeptic(state: AgentState) -> str:
        v = state["verdict"]
        return (
            "hypothesis_ranker"
            if v["verdict"] == "object" and len(state["objections"]) <= MAX_LOOPS
            else "narrator"
        )

    g = StateGraph(AgentState)
    g.add_node("triage", triage)
    g.add_node("evidence_collector", evidence_collector)
    g.add_node("hypothesis_ranker", hypothesis_ranker)
    g.add_node("skeptic", skeptic)
    g.add_node("narrator", narrator)
    g.add_edge(START, "triage")
    g.add_conditional_edges("triage", after_triage, ["narrator", "evidence_collector"])
    g.add_edge("evidence_collector", "hypothesis_ranker")
    g.add_edge("hypothesis_ranker", "skeptic")
    g.add_conditional_edges("skeptic", after_skeptic, ["hypothesis_ranker", "narrator"])
    g.add_edge("narrator", END)
    return g.compile()


def _ranker_view(facts: dict[str, Any]) -> dict[str, Any]:
    """Facts for the prompt, minus the per-visit list (notes are summarized)."""
    v = dict(facts)
    if "field_notes" in v:
        fn = dict(v["field_notes"])
        fn["visits"] = [x for x in fn["visits"] if x["note"] and x["note"].lower() != "clear"]
        v["field_notes"] = fn
    return v


async def run_agents(
    site: str,
    llm_mode: str | None = None,
    queue: asyncio.Queue | None = None,
    trace_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the team on one gauge. Returns the final state plus trace path and totals."""
    m = llm.mode(llm_mode)
    rec = TraceRecorder(site, m, queue, trace_dir)
    t0 = time.perf_counter()
    rec.emit("run", "started", {"llm": m})
    try:
        state = await build_graph(rec).ainvoke({"site": site, "llm": m}, {"recursion_limit": 25})
    except Exception as e:
        rec.emit("run", "error", {"error": f"{type(e).__name__}: {e}"[:500]})
        raise
    usage = state.get("usage", [])
    totals = {
        "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
        "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
        "llm_calls": sum(1 for u in usage if u.get("model") != "fallback"),
        "fallbacks_used": sum(1 for u in usage if "llm_error" in u or "rejected" in u),
        "wall_seconds": round(time.perf_counter() - t0, 2),
    }
    rec.final = {"narration": state.get("narration"), "final": state.get("final"), **totals}
    rec.emit("run", "completed", rec.final)
    return {**state, "trace_path": str(rec.path), "run_id": rec.run_id, "totals": totals}


def run_sync(
    site: str, llm_mode: str | None = None, trace_dir: Path | None = None
) -> dict[str, Any]:
    return asyncio.run(run_agents(site, llm_mode, None, trace_dir))
