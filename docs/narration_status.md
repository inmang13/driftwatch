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
  note sentences and the lead; the note meaning must appear verbatim; Helene only inside its
  window; the first sentence must state Q = V × A; the check verdict words must appear; the
  event sentence must give the measured peak or "no measured high flow explains it".
- `evals/run_evals.py`: the Asheville "no mechanism words" check now skips the labelled note
  sentences, as the spec allows. `tests/test_api.py` pins the new Hepco replay default.

### Things to know
- **Helene is never named for the three sites.** The rule is "change date within 30 days after
  2024-09-27". Newport's change date is 2024-10-28, 31 days after, so Newport uses its flood
  context instead ("91,700 cfs on 2024-09-28"). Hepco (2024-12-17) and Asheville (2025-07-23)
  are well outside the window. A synthetic test covers the Helene branch. If you want Newport to
  say Helene, widen the window to 31+ days. That's a one-line change (`HELENE_WINDOW_DAYS`).
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
  claim naming Helene is skipped outside the Helene window (rule 4). Tests point
  `context.CONTEXT_DIR` at an empty dir, so they never see the committed files.
- Results: **Hepco has no usable lead.** Its one remaining item (Walters Dam) names Helene.
  **Newport's lead** is the Cocke County evacuation story. **Asheville's lead** is the I-26
  Connector bridge plans.

### Items I removed after checking each URL's title against its claim
| Site | Claim (as the model wrote it) | Why removed |
|---|---|---|
| 03455000 | TDOT advanced bridge construction across the French Broad River ... Newport Bypass | wbir.com returns 403 Access Denied, so the title couldn't be checked |
| 03459500 | Contractors mobilized to replace an I-40 bridge over the Pigeon River near Exit 15 | Title "All lanes of I-40 in Pigeon River Gorge now open" is about lanes reopening |
| 03459500 | Helene caused historic flooding along the Pigeon River, washing out I-40 (USACE PN) | PDF returns Access Denied, so there was no title to check |
| 03451500 | Contractors began in-water cofferdam construction ... for a municipal pipeline replacement | Title is a "$75M pump station upgrade", not a pipeline replacement |
| 03459500 | Helene caused catastrophic flooding along the Pigeon River in Haywood County (thispendentworld.com) | The page never names the Pigeon River or Haywood County; it's a general Helene blog post |
| 03459500 | The USGS deployed crews to repair damaged streamgages along the Pigeon River (USGS news) | National news release; the page never names the Pigeon River or Haywood County |

Domain-only titles on PDFs ("usgs.gov", "americanrivers.org") were replaced with the document's
real title from its USGS Pubs landing page or the PDF's first page. PDFs were checked with
`pdftotext`: each one names its station or river. Each kept item has a `reviewed` field.
**Weak but kept:** atmostorm.com for Mills, an aggregator page. Its title matches its claim, but
it isn't a primary source. The Hepco Gemini trace was recorded before the last two removals, so
its evidence step still lists them; the narration used no lead for Hepco.

## LLM=gemini narrations (Replay defaults)

`traces/replay_defaults.json` now points at these runs. Gemini 3.8 Flash ran the ranker and the
narrator; the Skeptic ran on OpenRouter gpt-5.4-mini. All three texts below are Gemini's (none
fell back to the template), read from each trace's narrator payload:
- Hepco: the first attempt was rejected ("unit not spaced from its number ('1%')"); the retry
  passed.
- Newport: the first attempt was rejected ("204 words > 200"); the retry passed.
- Asheville: passed on the first attempt.

**French Broad River near Newport (03455000-20261108T014651910592Z.json):**
Flow equals water speed times cross-sectional area (Q = V × A); the curve assumes this holds at each stage. Since the 2024-10-28 visit, measurements at the French Broad River near Newport, USGS 03455000, sit 46 % below the rating; published flows run too high. The river stands 0.71 ft higher for the same flow: at 2.70 ft it carries 1,350 cfs (42 %) less than 3,210 cfs. The hydrographer noted "Fill control changed" on 2024-10-28. In the note's terms, gravel built up on the control (the riffle just downstream that sets the water level), so water backs up at the gauge: deeper, more area, much slower. Area changed +25 % and speed -58 %, so flow at the same level changed about -48 %, which agrees with the -42 % change. Between the 2024-08-19 and 2024-10-28 visits, flow reached 91,700 cfs on 2024-09-28. Possible lead: Cocke County ordered downtown Newport evacuated due to erroneous reports of a catastrophic dam failure during historic flooding (Flood top story of 2024). DriftWatch's agents rank fill first (83 %); the Skeptic accepted it. Double-check: Survey the control and apply a negative shift until two measurements agree. Rating confidence 30/100 (Stale).

**Pigeon River near Hepco (03459500-20261108T014651914025Z.json):**
Flow equals water speed times cross-sectional area (Q = V × A); the curve assumes this holds at each water level. Since the 2024-12-17 visit, field measurements at the Pigeon River near Hepco, USGS 03459500, have sat 33 % below the rating, so published flows run that much too high. The river now stands 0.33 ft higher for the same flow: at 2.33 ft it carries about 150 cfs (26 %) less than the curve's 570 cfs. The hydrographer noted "Scour control changed" on 2024-12-17. In the note's terms, the control (the riffle just downstream that sets the water level) eroded, so the same flow passes at a lower level. That disagrees with the data. Area changed -11 % and speed -22 %, so flow at the same level changed about -31 %, which agrees with the -26 % change. No gauging falls between the 2024-08-22 and 2024-12-17 visits, so no measured high flow explains it. DriftWatch's agents rank datum change / gauge rebuild first (44 %), but the Skeptic is under 60 % sure. Double-check: Resurvey the control section and benchmark/datum references at the gauge, and inspect for deposited material or downstream obstruction that could explain the 22.1 % velocity drop. Rating confidence 24/100 (Stale).

**French Broad River at Asheville (03451500-20261108T014651933246Z.json):**
Flow equals water speed times cross-sectional area (Q = V × A), which the curve assumes holds at each level. Since 2025-07-23, measurements at the French Broad River at Asheville, USGS 03451500, sat 41 % above the rating, so published flows run too low. The river stands 0.27 ft lower for the same flow: at 1.51 ft it carries 440 cfs (46 %) above the curve's 960 cfs. On 2025-07-23, the hydrographer noted "Debris - Light". In the note's terms, debris blocked the control (the riffle just downstream that sets the water level), raising the level until it clears. That disagrees with the data. Area changed +8 % and speed +2 %, so flow at the same level changed about +10 %, which does not back up the +46 % change. Between the 2025-06-03 and 2025-07-23 visits, no measured high flow explains it. Possible lead: Officials updated bridge construction plans across the French Broad River in Buncombe County for the Interstate 26 Connector project (I-26 Connector Plans Take Major Step Forward). No field note confirms what changed, so the cause remains open. Double-check: Measure flow and run levels from reference marks to the gauge before adjusting the rating. Rating confidence 46/100 (Stale).

### Worth a look
- Hepco's final cause flipped from fill (the fallback) to **datum change** under Gemini (44 %). The
  Skeptic's own recommended check (it writes the Double-check text) still points at deposited
  material. The Disagreement path is working as designed, but the ranked cause moves between runs.
- The Hepco Double-check quotes "22.1 % velocity drop". The Skeptic wrote that figure from the
  channel facts (−22.1 %), not the narrator, but the guard doesn't check Skeptic-written numbers.
- Newport's lead (the false dam-failure evacuation) is true and sourced, but it says nothing
  about the rating. Construction leads would be better there; the search found one (Newport
  Bypass), but its page blocks automated reads, so I removed it.
