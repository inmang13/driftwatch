"""DriftWatch API and console. `make serve` -> http://localhost:8000/

GET  /gauges            site, name, band, score, plus the trace Replay would use
GET  /report/{site}     Report + plot payload (points, base curve, Helene date)
POST /run/{site}        run the agent team now; TraceEvents as SSE (LLM from the env / .env)
GET  /trace/{id}        a saved trace (id = file stem, or a site id for its replay trace)
GET  /replay/{id}       a saved trace re-streamed as SSE, ~0.6 s between events (?pace=0 for tests)
GET  /registry          the module specs, live first
GET  /                  console.html

Every stream ends with a `finding` event: the finding card's data (cause status, Disagreement
rows, narration). CORS_ORIGINS (comma-separated) turns on CORS for those origins only.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
from functools import cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from driftwatch.agents import trace as tr
from driftwatch.agents.fallbacks import confidence_word
from driftwatch.modules.rating_curve import causes, pairing, rating
from driftwatch.modules.rating_curve import report as rc_report
from driftwatch.modules.rating_curve.usgs import SITES
from driftwatch.modules.registry import load_registry

load_dotenv()  # LLM / credentials from .env; never overrides the shell

HERE = Path(__file__).resolve().parent
CONSOLE = HERE / "console.html"
HELENE = "2024-09-27"
REPLAY_PACE_S = float(os.environ.get("REPLAY_PACE", "0.6"))
TRACE_ID = re.compile(r"^\d{8}-\d{8}T\d{6,12}Z$")  # <site>-<YYYYMMDDTHHMMSSffffffZ>
SITE_ID = re.compile(r"^\d{8}$")

app = FastAPI(title="DriftWatch", version="0.1.0")
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST"], allow_headers=["*"]
    )


# ---------- helpers ----------


def _check_site(site: str) -> str:
    if site not in SITES:
        raise HTTPException(404, f"unknown site {site!r}")
    return site


def _clean(x: Any) -> Any:
    """NaN/inf -> None, recursively (JSON has no NaN)."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_clean(v) for v in x]
    return x


def _trace_path(trace_id: str) -> Path:
    """File stem or site id -> a trace file inside the trace dir. Rejects anything else."""
    d = tr.trace_dir()
    if SITE_ID.match(trace_id):
        p = tr.latest_trace(_check_site(trace_id), d)
        if p is None:
            raise HTTPException(404, f"no saved trace for {trace_id}")
        return p
    if not TRACE_ID.match(trace_id):
        raise HTTPException(400, "bad trace id")
    p = d / f"{trace_id}.json"
    if not p.exists():
        raise HTTPException(404, f"no trace {trace_id}")
    return p


def _post_shift_notes(doc: dict[str, Any]) -> list[str]:
    """Distinct field notes the evidence collector found since the reference window."""
    for e in doc.get("events", []):
        p = e.get("payload", {})
        if p.get("tool") == "field_notes":
            return list(p.get("result", {}).get("distinct_notes") or [])
    return []


def finding(doc: dict[str, Any]) -> dict[str, Any]:
    """The finding card's data from a saved trace.

    cause_status:
      none          Trusted: triage sent the gauge straight to the narrator, no cause named
      disagreement  the skeptic's final verdict was a Disagreement (four rows on the card)
      corroborated  a field note since the reference window maps to the final cause
      open          a cause was ranked, but no field note backs it and there is no Disagreement
    """
    fin = (doc.get("final") or {}).get("final")
    notes = _post_shift_notes(doc)
    out: dict[str, Any] = {
        "trace_id": Path(doc.get("_path", "")).stem or None,
        "site": doc.get("site"),
        "llm": doc.get("llm"),
        "started_at": doc.get("started_at"),
        "narration": (doc.get("final") or {}).get("narration"),
        "cause": None,
        "confidence": None,
        "first_cause": None,
        "objections": 0,
        "cause_status": "none",
        "supporting_notes": [],
        "disagreement": None,
    }
    if not fin:
        return out
    cause = fin.get("cause")
    support = [n for n in notes if (c := causes.cause_for_note(n)) and c.key == cause]
    out.update(
        cause=cause,
        confidence=fin.get("confidence"),
        first_cause=fin.get("first_cause"),
        objections=fin.get("objections", 0),
        supporting_notes=support,
        skeptic_argument=fin.get("skeptic_argument"),
    )
    conf = fin.get("confidence")
    out["confidence_word"] = confidence_word(conf) if conf is not None else None
    if fin.get("disagreement"):
        out["cause_status"] = "disagreement"
        out["disagreement"] = fin["disagreement"]
        out["confidence_word"] = "uncertain"
    elif support:
        out["cause_status"] = "corroborated"
    else:
        out["cause_status"] = "open"
    return out


def _load(path: Path) -> dict[str, Any]:
    doc = tr.load_trace(path)
    doc["_path"] = str(path)
    return doc


def _trace_info(site: str) -> dict[str, Any] | None:
    p = tr.latest_trace(site, tr.trace_dir())
    if p is None:
        return None
    doc = tr.load_trace(p)
    return {"id": p.stem, "started_at": doc.get("started_at"), "llm": doc.get("llm")}


@cache
def _report(site: str):
    return rc_report.build_report(site, "snapshot")


@cache
def _report_payload(site: str) -> dict[str, Any]:
    """Report + everything the two plots need. Built from the snapshot, cached (it is static)."""
    rep = _report(site)
    ds = pairing.load_dataset(site, "snapshot")
    rel = rep.relationship
    top = rc_report.top_shift(rel.reference_end, rep.drift)
    split = top.time if top else None
    rows = rating.residual_table(rel, rc_report.visits_since_reference(ds))
    points = []
    for r in rows:
        t = r["time"]
        if t.date() <= rel.reference_end:
            period = "reference"
        elif split is None or t >= split:
            period = "post_shift"
        else:
            period = "between"  # after the reference window, before the detected shift
        points.append({**r, "time": t.isoformat(), "period": period})
    stages = [r["stage_ft"] for r in rows if r["stage_ft"] > rel.e]
    curve = []
    if stages:
        lo, hi = max(rel.e + 0.01, min(stages) * 0.9), max(stages) * 1.05
        n = 80
        for i in range(n + 1):
            h = lo + (hi - lo) * i / n
            curve.append({"stage_ft": h, "discharge_cfs": float(rating.predict_q(rel, h))})
    return _clean(
        {
            "report": json.loads(rep.model_dump_json()),
            "points": points,
            "curve": curve,
            "top_shift": json.loads(top.model_dump_json()) if top else None,
            "helene": HELENE,
            "split_time": split.isoformat() if split else None,
        }
    )


def _sse(ev) -> dict[str, str]:
    return {"event": "trace", "data": ev.model_dump_json()}


# ---------- routes ----------


@app.get("/gauges")
def gauges() -> list[dict[str, Any]]:
    out = []
    for site in SITES:
        rep = _report(site)
        out.append(
            {
                "site": site,
                "name": rep.site_name,
                "band": rep.trust.band,
                "score": rep.trust.score,
                "replay": _trace_info(site),
            }
        )
    return out


@app.get("/report/{site}")
def report(site: str) -> dict[str, Any]:
    return _report_payload(_check_site(site))


@app.get("/trace/{trace_id}")
def trace(trace_id: str) -> dict[str, Any]:
    doc = _load(_trace_path(trace_id))
    doc["finding"] = finding(doc)
    doc["id"] = Path(doc.pop("_path")).stem
    return doc


@app.get("/replay/{trace_id}")
async def replay(trace_id: str, pace: float | None = Query(None, ge=0, le=5)):
    path = _trace_path(trace_id)
    doc = _load(path)
    delay = REPLAY_PACE_S if pace is None else pace

    async def gen():
        yield {
            "event": "meta",
            "data": json.dumps(
                {
                    "replay": True,
                    "id": path.stem,
                    "started_at": doc.get("started_at"),
                    "llm": doc.get("llm"),
                    "site": doc.get("site"),
                }
            ),
        }
        for i, ev in enumerate(tr.replay(path)):
            if i and delay:
                await asyncio.sleep(delay)
            yield _sse(ev)
        yield {"event": "finding", "data": json.dumps(finding(doc))}

    return EventSourceResponse(gen())


@app.post("/run/{site}")
async def run(site: str):
    _check_site(site)
    from driftwatch.agents import llm
    from driftwatch.agents.graph import run_agents

    mode = llm.mode(None)
    queue: asyncio.Queue = asyncio.Queue()

    async def gen():
        yield {"event": "meta", "data": json.dumps({"replay": False, "site": site, "llm": mode})}
        task = asyncio.create_task(run_agents(site, mode, queue))
        while True:
            get = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({get, task}, return_when=asyncio.FIRST_COMPLETED)
            if get in done:
                ev = get.result()
                yield _sse(ev)
                if ev.node == "run" and ev.status in ("completed", "error"):
                    break
                continue
            get.cancel()
            if task.exception() is not None:  # failed before it could emit "run error"
                err = f"{type(task.exception()).__name__}: {task.exception()}"[:500]
                yield {"event": "error", "data": json.dumps({"error": err})}
                return
        try:
            out = await task
        except Exception as e:  # noqa: BLE001 - the stream must report any failure
            yield {"event": "error", "data": json.dumps({"error": f"{type(e).__name__}: {e}"})}
            return
        doc = _load(Path(out["trace_path"]))
        yield {"event": "finding", "data": json.dumps(finding(doc))}

    return EventSourceResponse(gen())


@app.get("/registry")
def registry() -> list[dict[str, Any]]:
    return [s.model_dump() for s in load_registry()]


@app.get("/", include_in_schema=False)
def console():
    return FileResponse(CONSOLE, media_type="text/html")
