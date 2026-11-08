# Narration status (branch m2-narration, 2026-11-07)

Both phases are done and pushed. `make test` passes (176 tests), `make demo` passes offline, and
`make evals` gives 11/13 with LLM=fallback, the same two Eno failures as on main.

## Phase A: report-voice narration

- `driftwatch/agents/narration.py` (new): the narrator facts are computed in code, plus the fixed
  sentences and the guard (`check_text`, `banned`).
- `fallbacks.narrate` builds the template from those sentences. `graph.narrator` sends the facts
  and the sentences to the LLM and checks its text. On a guard hit it retries once, telling the
  model why the text was rejected, and then falls back to the template. Every attempt and the
  narration facts go into the narrator's trace payload.
- The closing sentence is now "Rating confidence N/100 (Band).". The triage `score_display`
  ("Trust score ...") is unchanged, so the console is unaffected.
- The cap went from 120 to 200 words. Bare symbols (`%`, `=`, `×`) don't count as words. The
  fallbacks run 179–185 words.
- Guard rules: 200 words; ends on the rating sentence; banned words and patterns (rule 7, plus
  "the team" and "amount of water"); the open-cause rule, checked after removing the labelled
  note sentences and the lead; the note meaning must appear verbatim; Helene named only when
  `helene` is true, and then the Helene event sentence verbatim; the first sentence must state
  Q = V × A; the check verdict words must appear; otherwise the event sentence must give the
  measured peak or "no measured high flow explains it".
- `evals/run_evals.py`: the Asheville "no mechanism words" check now skips the labelled note
  sentences, as the spec allows. `tests/test_api.py` pins the new Hepco replay default.

### Things to know
- **Helene rule (changed 2026-11-07, replaces the 30-day window):** `helene` is true when the
  last visit before the change is before 2024-09-27 and the change visit (the first tested visit
  after it) is after it. "Tested" means the visits the drift test uses, so the Poor storm
  gaugings left out of the test don't count as visits. Newport (2024-08-19 / 2024-10-28) and
  Hepco (2024-08-22 / 2024-12-17) are true. Asheville (2025-06-03 / 2025-07-23) is false.
- **Event sentence when `helene` is true:**
  - No gauging in the gap (Hepco): "Hurricane Helene (2024-09-27) passed between the 2024-08-22
    and 2024-12-17 visits; no gauging was made during the storm."
  - **Newport differs from the spec on purpose.** Its gap holds two storm gaugings (2024-09-27
    and 2024-09-28, both rated Poor and left out of the drift test). "No gauging was made during
    the storm" next to the 91,700 cfs peak would contradict itself, so the clause names them
    instead: "...; the only gaugings during the storm were rated Poor, the largest 91,700 cfs on
    2024-09-28." To use your wording, change one line in `narration.helene_event`.
  - A non-storm gauging in the gap gets "...; no gauging was made during the storm, and the
    largest flow gauged between the visits was X cfs on D." No current site hits this case.
- The Helene sentence is fixed text. The prompt tells Gemini to copy it verbatim and the guard
  checks it word for word, because Gemini paraphrased it ("without storm gaugings") before that.
- Tests: the old-window synthetic test is kept (its cases flip: 23 days after is now false, the
  real 31-day Newport change is now true), and a new `test_helene_visit_rule` covers the rule.
- 15-point check: Newport −47.8 % vs −42.2 % (agrees), Hepco −30.9 % vs −25.6 % (agrees),
  Asheville +9.5 % vs +46.2 % (does not back up).
- Which field note gets explained: the note at the change visit if it has a fixed meaning, else
  the first "control changed" note, else the latest note with a meaning. Only Fill, Scour and
  Debris have a meaning. Other notes (Vegetation, Submerged, Clear) get no note sentence.
- "Lists of three adjectives" is a heuristic: three comma-listed words with adjective suffixes. A
  spaced hyphen is allowed because field notes are written "Debris - Light".
- The worktree has no venv of its own, so `make test`, `make demo` and `make context` were run
  from `..\AIHackathon-narration` with `PY=..\AIHackathon\.venv\Scripts\python.exe`.

## Phase B: cached event context

- `driftwatch/agents/context.py`: `load()` is the only part an agent run touches. It reads
  `data/context/<site>.json` and never searches. `make context SITE=...` runs Gemini on Vertex
  with Google Search grounding (supported in the installed langchain-google-vertexai 3.2.5).
  Three queries are built in code from the river, place, county, state and the visit window:
  storms/floods, dams/construction near the gauge, and USGS reports. A finding is kept only if a
  grounding chunk supports it. The grounding redirect is resolved to the real URL and the page's
  own `<title>` is fetched. Items whose page (title plus text) doesn't name the river or county
  are dropped. Claims and titles are cleaned of dashes, `| ? !` and parentheses.
- **Fixed after the files were made:** the first version of that filter tested the model's own
  claim, so it let everything through. It now tests the fetched page, which also drops PDFs and
  blocked pages (no text). The committed JSONs were made before this fix and then checked by
  hand (below), so a rerun of `make context` will keep fewer items.
- The evidence collector adds an `event_context` tool result, so the trace carries the URLs. The
  console has no code change; it shows the new step as a plain "event_context" row.
- Lead choice (`narration.pick_lead`): construction, then dam, then USGS report, then storm. A
  claim naming Helene is skipped unless `helene` is true (rule 4). Tests point
  `context.CONTEXT_DIR` at an empty dir, so they never see the committed files.
- Leads used now: Hepco gets the Walters Dam item (allowed, since `helene` is true for
  Hepco). Newport gets the 1960 USGS water-supply paper. Asheville gets the I-26 Connector
  bridge plans.
- The Cocke County evacuation item was taken out of `data/context/03455000.json` and moved to
  `removed_on_review` with `reviewed: false`, reason "not about the rating".

### Items I removed after checking each URL's title against its claim
| Site | Claim (as the model wrote it) | Why removed |
|---|---|---|
| 03455000 | TDOT advanced bridge construction across the French Broad River ... Newport Bypass | wbir.com returns 403 Access Denied, so the title couldn't be checked |
| 03459500 | Contractors mobilized to replace an I-40 bridge over the Pigeon River near Exit 15 | Title "All lanes of I-40 in Pigeon River Gorge now open" is about lanes reopening |
| 03459500 | Helene caused historic flooding along the Pigeon River, washing out I-40 (USACE PN) | PDF returns Access Denied, so there was no title to check |
| 03451500 | Contractors began in-water cofferdam construction ... for a municipal pipeline replacement | Title is a "$75M pump station upgrade", not a pipeline replacement |
| 03459500 | Helene caused catastrophic flooding along the Pigeon River in Haywood County (thispendentworld.com) | The page never names the Pigeon River or Haywood County; it's a general Helene blog post |
| 03459500 | The USGS deployed crews to repair damaged streamgages along the Pigeon River (USGS news) | National news release; the page never names the Pigeon River or Haywood County |
| 03455000 | Cocke County ordered downtown Newport evacuated due to erroneous reports of a dam failure | Not about the rating (Grace, 2026-11-07); marked `reviewed: false` |

Domain-only titles on PDFs ("usgs.gov", "americanrivers.org") were replaced with the document's
real title from its USGS Pubs landing page or the PDF's first page. PDFs were checked with
`pdftotext`: each one names its station or river. Each kept item has a `reviewed` field.
**Weak but kept:** atmostorm.com for Mills, an aggregator page. Its title matches its claim, but
it isn't a primary source. The Hepco Gemini trace was recorded before the last two removals, so
its evidence step still lists them. The current Hepco trace (below) was recorded after them.

## LLM=gemini narrations (Replay defaults)

`traces/replay_defaults.json` points at these runs. The Newport and Hepco runs below were redone
after the Helene rule change, and Asheville is unchanged. All three texts are Gemini 3.8 Flash
narrations (none fell back to the template), read from each trace's narrator payload.

**The Skeptic did not run on OpenRouter for Newport and Hepco.** OpenRouter returned 402 ("can
only afford 1970 tokens"), so the Skeptic used the deterministic rules in both runs. The ranker
and narrator were still Gemini. Asheville's run (earlier) had the OpenRouter Skeptic.

- Newport: the first narration attempt was rejected ("222 words > 200"); the retry passed.
- Hepco: the first narration attempt was rejected ("212 words > 200"); the retry passed.
- Asheville: passed on the first attempt.

**French Broad River near Newport (03455000-20261108T022812744607Z.json):**
Flow equals water speed times cross-sectional area (Q = V × A), assumed at each level. Since 2024-10-28, measurements at the French Broad River near Newport, USGS 03455000, sit 46 % below the rating, standing 0.71 ft higher for the same flow: at 2.70 ft it carries 1,350 cfs (42 %) below 3,210 cfs. The hydrographer noted "Fill control changed" on 2024-10-28. In the note's terms, gravel built up on the control (the riffle just downstream that sets the water level), so water backs up at the gauge: deeper, more area, much slower. Area changed +25 % and speed -58 %, so flow at the same level changed about -48 %, which agrees with the -42 % change. Hurricane Helene (2024-09-27) passed between the 2024-08-19 and 2024-10-28 visits; the only gaugings during the storm were rated Poor, the largest 91,700 cfs on 2024-09-28. Possible lead: A USGS water-supply paper documented hydrologic streamflow records for streamgage 03455000 on the French Broad River in Cocke County (Surface water supply of the United States, 1960, Part 3-B, Cumberland and). DriftWatch's agents rank fill first (82 %); the Skeptic agreed. Double-check: Survey the control and shift negatively until measurements agree. Rating confidence 30/100 (Stale).

**Pigeon River near Hepco (03459500-20261108T022812744003Z.json):**
Flow equals water speed times cross-sectional area (Q = V × A), which the curve assumes holds at each stage. Since the 2024-12-17 visit, measurements at the Pigeon River near Hepco, USGS 03459500, sat 33 % below the rating. The river stands 0.33 ft higher for the same flow, carrying 150 cfs (26 %) less at 2.33 ft. The hydrographer noted "Scour control changed" on 2024-12-17. In the note's terms, the control (the riffle just downstream that sets the water level) eroded, so the same flow passes at a lower level. That disagrees with the data. Area changed -11 % and speed -22 %, so flow at the same level changed about -31 %, which agrees with the -26 % change. Hurricane Helene (2024-09-27) passed between the 2024-08-22 and 2024-12-17 visits; no gauging was made during the storm. Possible lead: Duke Energy opened floodgates at Walters Dam to release surging Pigeon River waters during Hurricane Helene (Walters hydro plant turns 100: Dam, powerhouse withstood Helene's onslaught). DriftWatch's agents rank fill first (35 %); the Skeptic is under 60 % sure. Double-check: Survey the control for deposited gravel and check the gauge datum against the reference mark. Rating confidence 24/100 (Stale).

**French Broad River at Asheville (03451500-20261108T014651933246Z.json):**
Flow equals water speed times cross-sectional area (Q = V × A), which the curve assumes holds at each level. Since 2025-07-23, measurements at the French Broad River at Asheville, USGS 03451500, sat 41 % above the rating, so published flows run too low. The river stands 0.27 ft lower for the same flow: at 1.51 ft it carries 440 cfs (46 %) above the curve's 960 cfs. On 2025-07-23, the hydrographer noted "Debris - Light". In the note's terms, debris blocked the control (the riffle just downstream that sets the water level), raising the level until it clears. That disagrees with the data. Area changed +8 % and speed +2 %, so flow at the same level changed about +10 %, which does not back up the +46 % change. Between the 2025-06-03 and 2025-07-23 visits, no measured high flow explains it. Possible lead: Officials updated bridge construction plans across the French Broad River in Buncombe County for the Interstate 26 Connector project (I-26 Connector Plans Take Major Step Forward). No field note confirms what changed, so the cause remains open. Double-check: Measure flow and run levels from reference marks to the gauge before adjusting the rating. Rating confidence 46/100 (Stale).

### Worth a look
- Hepco's ranked cause moves between Gemini runs: datum change (44 %) in the earlier run, fill
  (35 %) in this one. The Disagreement path is working as designed.
- Newport's new lead (a 1960 USGS water-supply paper) is real but says nothing about the
  rating. Its title is cut at 12 words ("... Part 3-B, Cumberland and"). Construction leads
  would be better; the search found one (Newport Bypass), but its page blocks automated reads.
- Newport's Gemini text dropped "so published flows run that much too high". The guard
  doesn't require that clause.
