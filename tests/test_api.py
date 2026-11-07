"""API tests. Offline: LLM=fallback (conftest), replay at pace 0, runs write to tmp_path."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from driftwatch.api import app as api

REPO = Path(__file__).resolve().parents[1]
HEPCO_RUN4 = "03459500-20261107T180218430129Z"


def sse_events(text: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into (event, data) pairs."""
    out = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        ev, data = "message", []
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].lstrip())
        if data:
            out.append((ev, json.loads("\n".join(data))))
    return out


@pytest.fixture
def client():
    return TestClient(api.app)


def test_gauges(client):
    g = client.get("/gauges").json()
    assert len(g) == 8
    by = {x["site"]: x for x in g}
    assert by["03455000"]["band"] == "Stale"
    assert by["03451000"]["band"] == "Trusted"
    assert by["03459500"]["replay"]["id"] == HEPCO_RUN4  # replay_defaults.json wins


def test_report_has_plot_payload_and_valid_json(client):
    r = client.get("/report/03459500")
    assert r.status_code == 200
    body = json.loads(r.text)  # strict JSON: no NaN
    assert body["report"]["trust"]["band"] == "Stale"
    periods = {p["period"] for p in body["points"]}
    assert {"reference", "post_shift"} <= periods
    assert len(body["curve"]) > 10
    assert body["helene"] == "2024-09-27"
    assert body["split_time"].startswith("2024-12-17")
    newport = client.get("/report/03455000").json()
    assert sum(p["excluded"] for p in newport["points"]) == 2  # Helene gaugings kept for plots


def test_report_unknown_site(client):
    assert client.get("/report/99999999").status_code == 404


def test_registry(client):
    reg = client.get("/registry").json()
    assert len(reg) == 8
    assert reg[0]["status"] == "live"
    assert all(r["status"] == "specified" for r in reg[1:])
    for slot in ("get_data", "expected_relationship", "drift_test", "likely_causes"):
        assert reg[0][slot]


@pytest.mark.parametrize("bad", ["..%2F..%2Fpyproject", "03459500-x", "replay_defaults"])
def test_trace_rejects_bad_ids(client, bad):
    assert client.get(f"/trace/{bad}").status_code in (400, 404)


def test_trace_by_id_and_by_site(client):
    a = client.get(f"/trace/{HEPCO_RUN4}").json()
    b = client.get("/trace/03459500").json()
    assert a["id"] == b["id"] == HEPCO_RUN4
    f = a["finding"]
    assert f["cause_status"] == "disagreement"
    d = f["disagreement"]
    assert d["field_note"]["note"] == "Scour control changed"
    assert d["best_guess"]["cause"] != "scour"
    assert d["why_they_disagree"] and d["recommended_check"]


def test_finding_status_per_gauge(client):
    status = {
        s: client.get(f"/trace/{s}").json()["finding"]["cause_status"]
        for s in ("03455000", "03446000", "03451500", "03451000")
    }
    assert status == {
        "03455000": "corroborated",  # fill + "Fill control changed"
        "03446000": "corroborated",  # debris + "Debris - ..." notes
        "03451500": "open",  # scour, but only debris notes: the cause is open
        "03451000": "none",  # Trusted
    }


def test_replay_matches_saved_events(client):
    r = client.get(f"/replay/{HEPCO_RUN4}?pace=0")
    evs = sse_events(r.text)
    assert evs[0][0] == "meta" and evs[0][1]["replay"] is True
    assert evs[-1][0] == "finding"
    trace = [d for e, d in evs if e == "trace"]
    saved = json.loads((REPO / "traces" / f"{HEPCO_RUN4}.json").read_text(encoding="utf-8"))
    assert [(t["seq"], t["node"], t["status"]) for t in trace] == [
        (e["seq"], e["node"], e["status"]) for e in saved["events"]
    ]


def test_run_streams_fallback_to_completion(client, tmp_path, monkeypatch):
    monkeypatch.setenv("TRACE_DIR", str(tmp_path))
    shutil.copy(REPO / "traces" / "replay_defaults.json", tmp_path / "replay_defaults.json")
    r = client.post("/run/03451000")
    evs = sse_events(r.text)
    assert evs[0][1]["llm"] == "fallback"
    trace = [d for e, d in evs if e == "trace"]
    assert trace[-1]["node"] == "run" and trace[-1]["status"] == "completed"
    assert evs[-1][0] == "finding" and evs[-1][1]["cause_status"] == "none"
    assert len(list(tmp_path.glob("03451000-*.json"))) == 1  # trace went to TRACE_DIR


def test_console_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "DriftWatch" in r.text


def test_error_paths(client):
    assert client.post("/run/99999999").status_code == 404
    assert client.get("/replay/not-a-trace").status_code == 400
    assert client.get("/replay/99999999").status_code == 404


def test_console_has_no_cdn_and_plotly_is_vendored(client):
    html = client.get("/").text
    assert "http://" not in html and "https://" not in html
    assert 'src="static/plotly.min.js"' in html
    js = client.get("/static/plotly.min.js")
    assert js.status_code == 200 and "plotly.js v2.35.2" in js.text[:200]
