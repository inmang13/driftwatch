"""M2 agent team, LLM=fallback, offline."""

import pytest

from driftwatch.agents import fallbacks, graph, llm, tools
from driftwatch.agents.models import (
    BestGuess,
    Disagreement,
    FieldNoteRef,
    Hypothesis,
    Narration,
    Ranking,
    SkepticVerdict,
)
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
    # a Disagreement would replace the last objection; switch it off to test the bound alone
    monkeypatch.setattr(fallbacks, "disagreement", lambda facts, ranking, conf: None)
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


# --- direction words, Disagreement, replay default ------------------------------------------


def test_direction_phrase_reaches_fallback_and_llm_input(runs):
    for s, phrase in ((HEPCO, "below the rating"), (ASHEVILLE, "above the rating")):
        facts = runs[s]["facts"]
        assert facts["triage"]["direction_phrase"] == phrase
        assert phrase in runs[s]["narration"]  # fallback narrator used it
        view = graph.narrator_view(facts)
        assert view["direction_phrase"] == phrase
        assert "recent_median_residual_pct" not in view and "direction" not in view
        rendered = llm.prompt("narrator_input", facts=graph._dump(view), final="null")
        assert phrase in rendered
    assert "above the rating" in runs[SWANNANOA]["narration"]


def test_hepco_fallback_disagrees_and_newport_does_not(runs):
    h = runs[HEPCO]
    assert h["verdict"]["verdict"] == "disagree"
    d = h["final"]["disagreement"]
    assert d["field_note"] == {"note": "Scour control changed", "date": "2024-12-17"}
    assert d["best_guess"]["confidence"] < fallbacks.DISAGREE_BELOW
    assert d["recommended_check"] and d["why_they_disagree"]
    assert "Double-check:" in h["narration"]
    ev = [e for e in replay(h["trace_path"]) if e.node == "skeptic" and e.status == "completed"]
    assert ev[-1].payload["disagreement"]["field_note"]["note"] == "Scour control changed"
    n = runs[NEWPORT]
    assert n["verdict"]["verdict"] == "accept" and n["final"]["disagreement"] is None
    assert "Double-check" not in n["narration"]


def test_narration_guard_requires_double_check_for_disagreement():
    facts = {"triage": {"score": 24.0}}
    final = {"disagreement": {"x": 1}}
    assert graph.narration_ok("Trust score 24/100.", facts, final)
    assert graph.narration_ok("Double-check: levels. Trust score 24/100.", facts, final) is None


def test_ranker_sees_channel_only_after_an_objection():
    facts = {"triage": {}, "channel_geometry": {"a": 1}, "field_notes": {"visits": []}}
    assert "channel_geometry" not in graph._ranker_view(facts)
    assert "channel_geometry" in graph._ranker_view(facts, channel=True)


def test_replay_default_file_wins_over_newest(tmp_path):
    import json

    from driftwatch.agents.trace import latest_trace

    (tmp_path / "03459500-20260101T000000000000Z.json").write_text("{}")
    (tmp_path / "03459500-20270101T000000000000Z.json").write_text("{}")
    assert latest_trace(HEPCO, tmp_path).name.startswith("03459500-2027")
    (tmp_path / "replay_defaults.json").write_text(
        json.dumps({HEPCO: "03459500-20260101T000000000000Z.json"})
    )
    assert latest_trace(HEPCO, tmp_path).name.startswith("03459500-2026")


def test_missing_credentials_degrade_to_rules_with_a_warning(monkeypatch, tmp_path):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    out = graph.run_sync(HEPCO, "gemini", tmp_path)  # must not raise
    assert out["totals"]["fallbacks_used"] >= 3 and out["totals"]["llm_calls"] == 0
    warns = [e.payload.get("warning") for e in replay(out["trace_path"]) if e.status == "completed"]
    assert any(w and "GOOGLE_CLOUD_PROJECT is not set" in w for w in warns)
    assert out["final"]["cause"] != "scour"


def test_fallback_ranker_scores_insufficient_data_with_few_visits():
    facts = {"triage": graph.triage_facts(HEPCO)}
    facts.update(graph.collect_evidence(HEPCO, facts["triage"]))
    assert "insufficient_data" not in {h.cause for h in fallbacks.rank(facts).hypotheses}
    facts["triage"] = {**facts["triage"], "n_visits_last_12_months": 2}
    hyps = {h.cause: h for h in fallbacks.rank(facts).hypotheses}
    assert hyps["insufficient_data"].confidence > 0
    assert hyps["insufficient_data"].sign_matches


# --- structured narration (B), narrator facts (C), Disagreement parity (E) -----------------


def _facts(site):
    f = {"triage": graph.triage_facts(site)}
    if f["triage"]["band"] != "Trusted":
        f.update(graph.collect_evidence(site, f["triage"]))
    return f


def test_fallback_narration_passes_the_structured_guard(runs):
    for r in runs.values():
        parts = [e for e in replay(r["trace_path"]) if e.node == "narrator"][-1].payload["parts"]
        n = Narration.model_validate(parts)
        assert graph.narration_ok(n, r["facts"], r["final"]) is None
        assert n.direction == r["facts"]["triage"]["direction_phrase"]


def test_llm_narration_with_wrong_direction_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "backend", lambda role, mode: (object(), "fake"))
    facts = _facts(SWANNANOA)

    async def fake(role, mode, schema, system, user):
        if schema is Narration:
            t = facts["triage"]
            n = Narration(
                direction="below the rating",  # wrong: Swannanoa sits above
                confidence_word="n/a",
                cause_or_disagreement="No shift.",
                action="Keep visiting.",
                score_sentence=t["score_display"],
                text=f"Measurements sit 7 % below the rating. {t['score_display']}",
            )
            return n, {"model": "fake"}
        raise RuntimeError("rules")

    monkeypatch.setattr(llm, "structured", fake)
    out = graph.run_sync(SWANNANOA, "gemini", tmp_path)
    ev = [e for e in replay(out["trace_path"]) if e.node == "narrator"][-1].payload
    assert "direction must be" in ev["rejected"]
    assert "above the rating" in out["narration"]  # fell back to the template


def test_narrator_view_has_trusted_facts_and_no_signed_numbers():
    v = graph.narrator_view(_facts(SWANNANOA))
    for k in ("days_since_last_visit", "n_visits_last_12_months", "latest_control_note"):
        assert k in v
    assert v["recent_median_residual"].endswith("above the rating")
    assert "score_deductions" not in v and "recent_median_residual_pct" not in v
    prompt = llm.prompt("narrator").lower()
    assert "do not mention anything not in facts" in prompt
    assert "do not describe mechanisms" in prompt


def test_fallback_and_llm_disagreements_share_one_type(monkeypatch, tmp_path):
    fb = graph.run_sync(HEPCO, "fallback", tmp_path)
    monkeypatch.setattr(llm, "backend", lambda role, mode: (object(), "fake"))

    async def fake(role, mode, schema, system, user):
        # second review (an objection is on file): the LLM disagrees in its own words
        if schema is SkepticVerdict and '"verdict": "object"' in user:
            d = Disagreement(
                best_guess=BestGuess(cause="fill", confidence=0.3),
                field_note=FieldNoteRef(note="made up", date="1999-01-01"),
                why_they_disagree="LLM words.",
                recommended_check="LLM check.",
            )
            v = SkepticVerdict(verdict="disagree", argument="x", confidence=0.3, disagreement=d)
            return v, {"model": "fake"}
        raise RuntimeError("rules")

    monkeypatch.setattr(llm, "structured", fake)
    lm = graph.run_sync(HEPCO, "gemini", tmp_path)
    a, b = fb["final"]["disagreement"], lm["final"]["disagreement"]
    assert Disagreement.model_validate(a) and Disagreement.model_validate(b)
    assert set(a) == set(b)
    # the note and date always come from the field records, never from the model
    assert (
        b["field_note"]
        == a["field_note"]
        == {
            "note": "Scour control changed",
            "date": "2024-12-17",
        }
    )
    assert b["why_they_disagree"] == "LLM words."
