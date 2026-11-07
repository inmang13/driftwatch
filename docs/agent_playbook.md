# DriftWatch — agent playbook

> How and where each agent is used, with paste-ready prompts, and what the human does meanwhile. Pair with `docs/plan.md` (v2). Written Fri 2026-11-06 10 pm.

## A. Rules that apply to every agent session

1. **Every session starts with:** "Read `CLAUDE.md`, `docs/plan.md` §4 and §7, and `docs/agent_playbook.md` section for this stage. Summarize in 5 lines what you will build and what 'done' means, then wait for my OK." (Skip the wait only in unattended Pi jobs.)
2. **Plans before code** for anything over ~100 lines. Ask for the file list and function signatures first.
3. **One stage per session.** Finish, run `make test` and `make demo`, commit, `/compact` or start a new session. Context rot is the main failure mode on a long day.
4. **Tests are the gate.** A session that cannot make `make test` and `make demo` pass rolls back to the last green commit rather than patching forward.
5. **Snapshot is the default.** No session may call the live USGS API except `usgs.py` when `SOURCE=live` is set explicitly.
6. **No LLM calls in tests.** Agent tests run with `LLM=fallback`.
7. **Commit messages:** `stage: what` (`m1: segmentation + trust score`). Commit at every green checkpoint, not at the end.
8. **Agents never edit `docs/plan.md`.** They append to `docs/decision_log.md` (dated) when they make a choice the plan left open.

## B. Repo `CLAUDE.md` (paste this at the repo root tonight)

```markdown
# DriftWatch — Triangle AI Hackathon build (Nov 6–8 2026)

Drift monitoring for calibrated engineering relationships. Module #1: USGS rating curves after Hurricane Helene.
Build contract: docs/plan.md (§4 architecture, §7 schedule). How to work: docs/agent_playbook.md. Decisions: docs/decision_log.md (append, dated).

## Stack
Python 3.11 · pydantic v2 · numpy/pandas/scipy · ruptures · LangGraph · langchain-google-vertexai (Gemini) · langchain-openai pointed at OpenRouter (skeptic) · FastAPI + sse-starlette · Plotly.js in one static page · pytest · black + ruff.
Package: `driftwatch/` (core, modules/rating_curve, modules/specs, agents, api). Data: `data/snapshot/<site>.json`. Traces: `traces/`.

## Commands
make install · make snapshot (SOURCE=live, only on request) · make report SITE=03459500 · make run SITE=03459500 (agents, writes trace) · make serve (FastAPI :8000, console at /) · make test · make evals · make demo (report + run on 03459500 and 03451000 with LLM=fallback; must pass offline)

## Non-negotiables
- Snapshot is the default source. Live USGS only with SOURCE=live.
- Pair each discharge with the reading_type='MeanGageHeight' stage row on (field_visit_id, time). A visit can hold several discharges.
- Never use channel area/velocity/width as predictors (Q = A·V leakage). Evidence only.
- Keep rating exponent b and offset e fixed from the base fit; drift = sliding a. Report shift in ft and %.
- Exclude measurements rated Poor taken 2024-09-26..28 from the drift test; keep them for plots.
- Residual sign convention: scour → positive; fill → negative; debris/vegetation → negative transient; datum change/rebuild → step of either sign with no channel evidence.
- Every LLM node has a deterministic fallback selected by LLM=fallback. Tests never call an LLM.
- Every agent run writes traces/<site>-<timestamp>.json; the API can replay a trace.
- Trust score is glass-box: the report includes each deduction and its reason.
- Sites: 03459500 03455000 03446000 03451500 03451000 03463300 03479000 02085000. Reference window for the base rating: 2012-01-01 .. 2024-09-25 (Eno: 2015-01-01 .. 2025-07-06).

## Done means
make test green · make demo green offline · Canton (03459500) and Newport (03455000) come out Stale with a documented cause · Swannanoa (03451000), North Toe (03463300), Eno (02085000) come out Trusted · README run instructions work from a clean clone.
```

## C. Tonight (Fri 10–11 pm) — human + Claude Code, laptop

**Human (10 min):** create the public GitHub repo `driftwatch`; copy `CLAUDE.md` (above), `docs/plan.md`, `docs/agent_playbook.md`, an empty `docs/decision_log.md`; `.gitignore` for `.env`, `traces/`, `.venv`; `.env.example` with `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`, `OPENROUTER_API_KEY`, `USGS_API_KEY`, `LLM=gemini|openrouter|fallback`, `SOURCE=snapshot|live`.

**Claude Code session 1 — M0 (30 min). Paste:**
> Read CLAUDE.md and docs/plan.md §3–§4. Build only this: (1) `pyproject.toml` + `Makefile` with the targets in CLAUDE.md (stub targets may print "not yet"); (2) `driftwatch/core/schemas.py` with pydantic models `Measurement`, `Dataset`, `Relationship`, `Shift`, `DriftResult`, `TrustScore` (with a `deductions: list[Deduction{name, points, reason}]` field), `Report`, `TraceEvent`; (3) `driftwatch/modules/rating_curve/usgs.py` that fetches `field-measurements`, `channel-measurements`, and `monitoring-locations` for one site from the OGC API, follows `next` links, and writes `data/snapshot/<site>.json` with the raw features; `load_snapshot(site)` reads it back; (4) `make snapshot SOURCE=live` runs it for the 8 sites in CLAUDE.md. Run it once now with SOURCE=live, commit the snapshot files, and print the row counts per site and collection. Do not build pairing, fitting, or anything else.

**Human (30 min, in parallel):** set up the Orange Pi: Claude Code logged in, `git clone` of the repo with push rights to branches (not main — protect main on GitHub), Python 3.11 + `make install`, `.env` with `LLM=fallback`. Test: `claude -p "run make test and report"` returns.

**Launch Pi job #1 at ~11 pm** (section D). Go to sleep.

## D. Orange Pi job #1 — Fri night, unattended (M1)

Run from the repo on the Pi, on a branch:
```
git checkout -b pi/m1
claude -p --permission-mode acceptEdits --max-turns 200 "$(cat docs/prompts/pi_job1.md)"
```
`docs/prompts/pi_job1.md`:
> You are building stage M1 of DriftWatch unattended overnight. Read CLAUDE.md, docs/plan.md §3–§4, and docs/agent_playbook.md section A. Nobody will answer questions: when the plan is silent, choose the simplest option, write one dated line in docs/decision_log.md, and continue.
> Build, in order, committing after each green step:
> 1. `pairing.py`: from the snapshot, one row per discharge measurement with stage (MeanGageHeight on the same field_visit_id and time), discharge, time (UTC), measurement_rated, control_condition, quality weight (Excellent 4, Good 3, Fair 2, Poor 1, else 1.5). Unit test with a 2-discharge visit fixture.
> 2. `rating.py`: weighted log-space power-law fit Q = a(H−e)^b on the reference window; `predict_q(H)`, `predict_h(Q)`; residual_pct and stage_shift_ft per measurement. Constrain e below the minimum reference stage. Unit test on Eno: MdAPE within the reference window < 10 %.
> 3. `segmentation.py`: Darienzo-style recursive segmentation — change points on the residual series with `ruptures` (Pelt, model="l2"), minimum segment 6 points, recurse until no change point improves the penalized cost; output stable periods and shifts {time, size_pct, size_ft, direction, n_after, confidence}. Choose the penalty so Eno and Swannanoa report no shift after 2024-09-26 and Newport reports one. Record the chosen penalty in decision_log.md.
> 4. `causes.py`: the cause catalog (scour, fill/aggradation, debris, vegetation, datum change/gauge rebuild, measurement quality, insufficient data) each with expected residual sign and the evidence fields an investigator should look at.
> 5. `core/trust.py`: the glass-box score exactly as plan §4; every deduction carries a reason string.
> 6. `cli.py` + `make report SITE=…`: writes `reports/<site>.json` (Report schema) and prints a one-line summary: site name, band, score, top shift.
> 7. `make test` green; `make demo` runs report for 03459500 and 03451000 offline.
> 8. Write `docs/m1_results.md`: a table of all 8 sites (band, score, shifts found, median post-2024-09-26 residual) and anything that surprised you.
> Stop when done or when any step fails twice; leave the branch pushed and a short `docs/m1_status.md` describing where you stopped. Never touch main.

## E. Saturday — session by session

### 8:00–9:30 · M1 review (human + Claude Code laptop + Codex)
- Human: read `docs/m1_results.md` and `docs/m1_status.md` first (5 min). Pull the branch, `make test`, `make demo`.
- Codex review #1, paste: *"Review branch pi/m1 of this repo against CLAUDE.md non-negotiables. List, ranked, anything that will produce a wrong trust score or a wrong shift: pairing errors, leakage, sign errors, unit mix-ups, timezone, penalty overfitting. Do not rewrite code; produce a checklist."*
- Claude Code session 2: fix the checklist, confirm Canton/Newport fire and controls stay quiet, merge to main.

### 9:30–1:00 · M2 agents (Claude Code laptop, worktree `backend`)
Paste:
> Read CLAUDE.md, plan §4 "Agents", playbook A. Build `driftwatch/agents/`: LangGraph `StateGraph` with nodes triage → evidence_collector → hypothesis_ranker → skeptic → narrator, conditional edges exactly as plan §4 (skeptic objection loops to ranker at most twice; triage on a healthy gauge goes straight to narrator). Tools in `tools.py` are pure Python over the Report + snapshot: `channel_geometry_trend(site, before, after)` (width, area, mean depth = area/width, velocity; before vs after the first shift), `field_notes(site, since)`, `flood_context(site)` (max discharge measured between the last in-period and first post-shift measurement; also the dataset's peak-of-record if it falls there), `site_metadata(site)`. LLM clients in `llm.py`: `gemini` (langchain-google-vertexai), `openrouter` (langchain-openai with base_url), `fallback` (rule-based: ranker picks the catalog cause whose sign matches and has the most evidence; skeptic accepts unless the sign mismatches; narrator fills a template). Structured outputs via pydantic. Every node emits TraceEvent to an asyncio queue and to `traces/`. `make run SITE=…` prints the narration and writes the trace. Tests with LLM=fallback on Canton, Newport, Swannanoa. Then run all 8 with LLM=gemini and summarize in `docs/m2_results.md`.
- **Human meanwhile:** write `docs/pitch.md` (3-minute script from plan §2) and start `docs/devpost.md`. Read the first Gemini narrations and fix tone in `prompts/` (utility-manager voice, no jargon, name the evidence).
- Codex review #2 at the end: *"Find places where an LLM output can crash the graph or where the fallback diverges from the LLM path."*

### 1:00–3:30 · M3 console (Claude Code, worktree `ui`)
Paste:
> Read plan §4 "UI". Build `driftwatch/api/app.py` (FastAPI): GET /gauges (band, score, name), GET /report/{site}, POST /run/{site} streaming TraceEvents as SSE, GET /trace/{id}, GET /replay/{id} (SSE at human pace), GET /registry (from modules/specs/*.yaml), static `console.html` at /. The page: left gauge list with band colors; center Plotly stage–discharge scatter (reference vs post-shift colored, base curve drawn) above a residual timeline with Helene (2024-09-27) and detected shift times as vertical lines; right a 5-box agent graph that highlights the running node plus a streaming log; bottom the finding card with the score arithmetic. Registry tab renders the YAML specs as cards (1 live, 7 specified). Vanilla JS, one file, phone-usable. `make serve`. Then run Canton end to end and screenshot.
- **Human meanwhile:** watch the first run on the page and note every moment that would confuse a judge; those become the prompt edits.

### 3:30–4:00 · Informer spike (human + Claude Code with the Informer plugin)
`npm install -g @entrinsik/informer-cli` → `inf login <team>.go.informer.cloud` → in Claude Code `/plugin marketplace add entrinsik-org/claude-plugins` → `/plugin install informer@entrinsik-plugins` → new folder `informer-app/` → prompt: *"Build a minimal Informer App with one page and one server route that GETs `<cloud-run-or-ngrok-url>/gauges` and shows the JSON. Deploy it."* Go if the deploy works and the route can reach your API. If Cloud Run isn't up yet, expose the laptop with ngrok for the spike.

### 4:00–6:30 · M4 product UI
- Go: Claude Code (Informer plugin) builds the app: gauge list with trust bands → gauge page with the finding card, score arithmetic, evidence, and an embedded/linked live console for the run → run history stored in Postgres via a server route that fetches `/trace/{id}` after a run → registry page. `inf deploy`. Optional if ahead: scheduled agent that re-runs nightly and a push notification on band change.
- No-go: polish `console.html`, add run history in memory, and make the registry tab shine.

### 6:30–8:00 · M5 deploy + evals
- Claude Code: Dockerfile for the Python service, `gcloud run deploy` (snapshot baked in, secrets via Secret Manager, CORS allowing the Informer origin), `make evals` producing `docs/eval_report.md`.
- Codex review #3: *"Pretend you are a judge opening the live URL on a phone for 90 seconds. What breaks or confuses?"* Fix the top three.

### 8:00–10:30 · freeze, write, record, submit
- 8:00 **freeze core/ and agents/**. Claude chat (this one): tighten README, DevPost text, slide text from `docs/pitch.md`.
- 9:00 record the video in one take: 20 s problem, 70 s Canton run, 20 s Swannanoa quiet, 10 s registry and evals. Screenshots. Submit DevPost by 10:30.
- Launch Pi job #2 (section F). Stop at 11.

## F. Orange Pi job #2 — Sat night, unattended (docs only)
Branch `pi/docs`. Prompt:
> Read CLAUDE.md and docs/plan.md. Do not modify anything under driftwatch/core or driftwatch/agents. Tasks: (1) complete `modules/specs/*.yaml` so all 7 specified modules have the four slots filled in two sentences each plus a `why_it_drifts` line and a `who_cares` line; (2) run `make evals` and write `docs/eval_report.md` with the pass/fail table, tokens and wall time per case; (3) README: clean-clone instructions verified by actually running them in a fresh venv, architecture diagram as Mermaid, the differentiation table from plan §2, the IDS 706 relationship note; (4) `docs/pitch_script.md`: a 3-minute script with timings from docs/pitch.md. Commit after each task; open a PR; stop.

## G. Sunday 8:00–8:30
Merge `pi/docs` if `make test` and `make evals` are green; otherwise merge only the README. Final DevPost edits. Done by 8:30. Judging runs from snapshot mode with Cloud Run as the URL; keep `make serve` running locally as the backup.

## H. Human-only jobs (things agents should not do)
- Decide the hero gauge after seeing M1 numbers (Canton vs Newport).
- Approve every narration's tone before it goes in the video.
- Judge the Informer go/no-go at 4:00 pm sharp.
- Keep `docs/decision_log.md` honest: every cut from the cut order gets a dated line.
- Eat, and stop at 11.
