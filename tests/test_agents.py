"""M2 agent team, LLM=fallback, offline."""

import pytest

from driftwatch.agents import fallbacks, graph, llm, tools
from driftwatch.agents.models import Hypothesis, Ranking, SkepticVerdict
from driftwatch.agents.trace import TraceRecorder, load_trace, replay
from driftwatch.modules.rating_curve import causes

HEPCO, NEWPORT, ASHEVILLE, SWANNANOA = "03459500", "03455000", "03451500", "03451000"


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    d = tmp_path_factory.mktemp("traces")
    return {s: graph.run_sync(s, "fallback", d) for s in (HEPCO, NEWPORT, ASHEVILLE, SWANNANOA)}


def test_graph_compiles(tmp_path):
    g = graph.build_graph(TraceRecorder("x", "fallback", out_dir=tmp_path))
    assert set(g.get_graph().nodes) >= {
        "triage",
        "evidence_collector",
        "hypothesis_ranker",
        "skeptic",
        "narrator",
    }


def test_hepco_skeptic_objects_and_final_is_not_plain_scour(runs):
    r = runs[HEPCO]
    assert len(r["objections"]) >= 1
    assert r["objections"][0]["objection"] == "channel_evidence"
    assert r["final"]["cause"] != "scour"


def test_newport_is_fill(runs):
    assert runs[NEWPORT]["final"]["cause"] == "fill"


def test_asheville_is_a_positive_sign_cause(runs):
    assert causes.get_cause(runs[ASHEVILLE]["final"]["cause"]).expected_sign == "positive"


def test_swannanoa_goes_straight_to_narrator_with_no_cause(runs):
    r = runs[SWANNANOA]
    assert r["final"] is None
    nodes = [e.node for e in replay(r["trace_path"])]
    assert "evidence_collector" not in nodes and "skeptic" not in nodes
    assert "94" in r["narration"]


def test_ranker_always_lists_datum_change_and_inconclusive(runs):
    for s in (HEPCO, NEWPORT, ASHEVILLE):
        for rk in runs[s]["rankings"]:
            keys = {h["cause"] for h in rk["hypotheses"]}
            assert {"datum_change", "inconclusive"} <= keys


def test_narrations_are_short_and_carry_the_score(runs):
    for r in runs.values():
        assert graph.narration_ok(r["narration"], r["facts"]) is None


def _stable(events):
    vol = {"wall_seconds", "seconds"}
    return [
        (e.seq, e.node, e.status, {k: v for k, v in e.payload.items() if k not in vol})
        for e in events
    ]


def test_replay_determinism(tmp_path):
    out = graph.run_sync(HEPCO, "fallback", tmp_path)
    replayed = list(replay(out["trace_path"]))
    assert replayed[0].node == "run" and replayed[-1].node == "run"
    assert replayed[-1].status == "completed"
    assert [e["seq"] for e in load_trace(out["trace_path"])["events"]] == list(range(len(replayed)))
    # replaying twice gives identical events
    assert list(replay(out["trace_path"])) == replayed
    # a second fallback run gives the same event stream (minus timing)
    out2 = graph.run_sync(HEPCO, "fallback", tmp_path)
    assert out2["trace_path"] != out["trace_path"]
    assert _stable(replay(out2["trace_path"])) == _stable(replayed)


def test_channel_geometry_hepco_shows_speed_falling_more_than_area():
    ch = tools.channel_geometry_trend(HEPCO, "2024-12-17T18:18:38+00:00")
    assert ch["sufficient"] and ch["n_after"] >= 10
    assert ch["velocity_change_pct"] < ch["area_change_pct"] < 0
    assert fallbacks.channel_signature(ch) == "backwater"


def test_channel_geometry_insufficient_when_split_is_too_late():
    ch = tools.channel_geometry_trend(HEPCO, "2026-10-10")
    assert ch["sufficient"] is False and ch["area_change_pct"] is None


def test_flood_context_asheville_gap_is_empty_and_hepco_spans_helene():
    a = tools.flood_context(ASHEVILLE, "2025-07-23T17:37:24+00:00")
    assert a["peak"] is None and a["helene_in_gap"] is False
    h = tools.flood_context(HEPCO, "2024-12-17T18:18:38+00:00")
    assert h["helene_in_gap"] is True


def test_field_notes_include_hepco_scour_note():
    assert "Scour control changed" in tools.field_notes(HEPCO)["distinct_notes"]


def test_clean_ranking_adds_required_and_drops_duplicates():
    facts = {"triage": graph.triage_facts(HEPCO)}
    facts.update(graph.collect_evidence(HEPCO, facts["triage"]))
    r = Ranking(
        hypotheses=[
            Hypothesis(cause="fill", confidence=0.7, sign_matches=False),
            Hypothesis(cause="fill", confidence=0.1, sign_matches=True),
            Hypothesis(cause="scour", confidence=0.2, sign_matches=True),
        ]
    )
    c = graph.clean_ranking(r, facts, [])
    keys = [h.cause for h in c.hypotheses]
    assert keys.count("fill") == 1 and {"datum_change", "inconclusive"} <= set(keys)
    assert {h.cause: h.sign_matches for h in c.hypotheses}["scour"] is False  # recomputed
    assert c.top.cause == "fill"


def test_narration_guard():
    facts = {"triage": {"score": 24.0}}
    assert graph.narration_ok("word " * 121 + "24", facts)
    assert graph.narration_ok("Trust score 30/100.", facts) == "the trust score is missing"
    assert graph.narration_ok("Trust score 24/100 (Stale).", facts) is None


def test_llm_failure_falls_back_and_is_recorded(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "backend", lambda role, mode: (object(), "fake"))

    async def boom(*a, **k):
        raise RuntimeError("model down")

    monkeypatch.setattr(llm, "structured", boom)
    out = graph.run_sync(HEPCO, "gemini", tmp_path)
    assert out["final"]["cause"] != "scour"
    assert out["totals"]["fallbacks_used"] >= 3
    errs = [
        e.payload.get("llm_error") for e in replay(out["trace_path"]) if e.status == "completed"
    ]
    assert any(e and "model down" in e for e in errs)


def test_skeptic_loop_is_bounded(monkeypatch, tmp_path):
    always = SkepticVerdict(
        verdict="object", objection="other", argument="no", suggested_cause="inconclusive"
    )
    monkeypatch.setattr(fallbacks, "critique", lambda facts, ranking: always)
    out = graph.run_sync(HEPCO, "fallback", tmp_path)
    assert len(out["objections"]) == graph.MAX_LOOPS + 1
    assert len(out["rankings"]) == graph.MAX_LOOPS + 1
    assert out["final"]["unresolved"] is True


def test_llm_mode_rejects_unknown():
    with pytest.raises(ValueError):
        llm.mode("gpt")


def test_wrong_sign_mismatch_label_is_relabelled(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "backend", lambda role, mode: (object(), "fake"))

    async def fake(role, mode, schema, system, user):
        if schema is SkepticVerdict:
            v = SkepticVerdict(
                verdict="object", objection="sign_mismatch", argument="x", suggested_cause="fill"
            )
            return v, {"model": "fake"}
        raise RuntimeError("use the rules")

    monkeypatch.setattr(llm, "structured", fake)
    out = graph.run_sync(HEPCO, "gemini", tmp_path)
    first = out["objections"][0]
    assert first["objection"] == "other"  # datum_change fits either sign
    guards = [e.payload.get("guard") for e in replay(out["trace_path"]) if e.node == "skeptic"]
    assert any(g and "relabelled" in g for g in guards)


def test_queue_receives_the_same_events_as_the_trace(tmp_path):
    import asyncio

    async def go():
        q = asyncio.Queue()
        out = await graph.run_agents(SWANNANOA, "fallback", q, tmp_path)
        got = []
        while not q.empty():
            got.append(q.get_nowait())
        return out, got

    out, got = asyncio.run(go())
    assert got == list(replay(out["trace_path"]))
    assert [e.seq for e in got] == list(range(len(got)))
