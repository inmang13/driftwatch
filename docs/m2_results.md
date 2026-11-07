# M2 results: what the agent team says about the 8 gauges

*Branch `m2-agents`, 2026-11-07, Gemini runs updated 12:12–12:20 pm. These are the Gemini runs, with traces in `traces/`. Ranker and
narrator ran on Vertex `gemini-3.8-flash`. The skeptic ran on OpenRouter `openai/gpt-5.4-mini`.
Every LLM call succeeded and no node fell back to the rules. The fallback runs (`LLM=fallback`)
are listed for comparison; `make test` and `make demo` use those.*

## Skeptic rule for a contradicted control note (added 12:10 pm)

Grace added a rule to `prompts/skeptic.md`: if the ranker's top cause contradicts a hydrographer's
note on the control, the skeptic objects once and asks the ranker to name the channel-geometry or
flood evidence that outweighs the note. It accepts on the next pass if the ranker does.

**Test result: the rule fires as asked.** Hepco (note: "Scour control changed") got an objection on
both Gemini runs. Newport ("Fill control changed", top cause fill) was accepted on the first pass.
Asheville and Mills, which have debris notes but no control-changed note, were also accepted.

**Side effect: Hepco no longer ends at fill.** In both runs Gemini's first pick was **datum change**,
not fill. That is not caused by the rule: the ranker prompt didn't change and the ranker
runs before the skeptic. At temperature 0, Gemini picked fill earlier today and datum change on
these two runs, so it is not deterministic.

| Hepco run | Round 1 | Skeptic | Round 2 | Skeptic | Round 3 | Skeptic | Final |
|---|---|---|---|---|---|---|---|
| 1 (12:12) | datum change 0.46 | objects: note says scour | datum change 0.45 | accepts | — | — | **datum change 0.45**, 1 objection, 58 s |
| 2 (12:13) | datum change 0.45 | objects: note + backwater pattern | fill 0.45 | objects: still not justified over the note | inconclusive 0.45 | accepts | **inconclusive 0.45**, 2 objections, 263 s |

**Two weak points in the round-2 accepts:**
- In run 1 the skeptic accepted because the ranker "now cites the geometry". It didn't: the ranker
  repeated its datum-change case and only added that scour has the wrong sign. The skeptic's own
  argument said the geometry favors fill over datum change, and then it accepted datum change.
- The ranker can't see the channel numbers. I hid them so that the skeptic's check is independent.
  So when the rule asks the ranker to "name the channel-geometry evidence", the ranker can only
  quote numbers back from the objection text. If the rule is supposed to make the ranker argue
  from geometry, show it the channel numbers on rounds after an objection.

The final cause is still never plain scour, which is the spec's requirement. Run 2 is the better
demo story: "the reviewer overturned the first diagnosis and the honest answer is inconclusive".
Run 1 ends on a cause that the skeptic's own argument contradicts. Both traces are in `traces/`.
Replay picks the newest file, which is run 2.

**Eval case (M5):** "Hepco → skeptic objects" now passes with Gemini. "Hepco final cause = fill"
does not, so use "final cause is not scour".

## Gemini run, per gauge (current prompts)

Key: **Final cause** is the team's answer after the skeptic, and **conf.** is the ranker's
confidence in it (0–1). **Objections** counts the times the skeptic sent the ranker back. **Tokens**
are input + output across all LLM calls in the run. **Wall** is seconds for the whole run,
including the M1 engine. Ranker and narrator: Vertex `gemini-3.8-flash`. Skeptic: OpenRouter
`openai/gpt-5.4-mini`. No node fell back to the rules.

| Site | Gauge | Band (score) | Final cause | Conf. | Objections | Tokens | Wall |
|---|---|---|---|---|---|---|---|
| 03459500 | Pigeon R near Hepco (run 1) | Stale (24) | datum change | 0.45 | 1 | 10,508 + 1,389 | 58 s |
| 03459500 | Pigeon R near Hepco (run 2) | Stale (24) | inconclusive | 0.45 | 2 | 15,885 + 2,277 | 263 s |
| 03455000 | French Broad near Newport | Stale (30) | fill | 0.82 | 0 | 6,337 + 815 | 22 s |
| 03446000 | Mills R | Watch (73) | debris | 0.55 | 0 | 5,930 + 708 | 24 s |
| 03451500 | French Broad at Asheville | Stale (46) | scour | 0.72 | 0 | 5,879 + 768 | 31 s |
| 03451000 | Swannanoa at Biltmore | Trusted (94) | none (straight to narrator) | — | — | 843 + 107 | 15 s |
| 03463300 | South Toe near Celo | Trusted (95) | none | — | — | 844 + 116 | 8 s |
| 03479000 | Watauga near Sugar Grove | Trusted (95) | none | — | — | 840 + 114 | 7 s |
| 02085000 | Eno at Hillsborough | Trusted (91) | none | — | — | 843 + 110 | 9 s |

Gemini latency swings a lot. Hepco run 2 made 6 LLM calls and took 263 s; Mills' ranker call
took 71 s on one earlier pass and 15 s on the next.

Earlier today, before the control-note rule, Gemini ranked Hepco fill 0.45 and the skeptic
accepted with no objection. Those traces have been replaced.

## Fallback run (`LLM=fallback`), for comparison

| Site | Final cause | Conf. | Skeptic |
|---|---|---|---|
| Hepco | fill | 0.60 | **objected once.** The first pick was datum change. The skeptic said "the water moves much slower while the section barely changed (area −11 %, speed −22 %)… fill or backwater on the control", and the ranker switched to fill. |
| Newport | fill | 0.44 | accepted (backwater pattern fits fill) |
| Mills | debris | 0.67 | accepted |
| Asheville | scour | 0.50 | accepted |
| 4 Trusted gauges | none | — | not run |

The fallback gives Newport lower confidence than Gemini does. Its debris and vegetation notes
each take a share.

## Channel geometry (`channel_geometry_trend`)

Key: each row compares channel measurements before and after the gauge's shift date, at the
same water level (the median post-shift stage). **Area** is the flow area of the measuring section
and **speed** is mean velocity, both as % change after vs before. **n** counts the channel
measurements used on each side. These numbers are evidence only and never go into the rating.

| Gauge | Split at | n before / after | At stage | Area | Speed | Median width before → after |
|---|---|---|---|---|---|---|
| Hepco | 2024-12-17 | 101 / 18 | 2.33 ft | **−11.3 %** | **−22.1 %** | 119 → 124.5 ft |
| Newport | 2024-10-28 | 80 / 15 | 2.70 ft | **+25.2 %** | **−58.3 %** | 375 → 382 ft |
| Asheville | 2025-07-23 | 116 / 10 | 1.51 ft | +7.7 % | +1.7 % | 303 → 312.5 ft |
| Mills | 2024-09-26 (no shift; storm date) | 162 / 16 | 1.97 ft | +22.5 % | −25.9 % | 69 → 69.8 ft |

**These replace the hand-computed numbers in `m1_results.md`.** The hand numbers were Hepco
area −5 % / speed −24 % and Newport +35 % / −51 %. The direction and the story are the same: at both
hero gauges the water slows much more than the section changes. The pitch should use the tool's numbers.

**Don't use channel % as a drift signal on its own.** Swannanoa (Trusted, rating held) also
shows area +12 % and speed −30 % after the storm. South Toe shows area +170 % (its median width
went from 79 to 103 ft, which looks like the crews measured at a different section after the
flood). The channel numbers help pick a *cause* once the rating has shifted. They don't detect
drift.

## Narration notes (for tone edits in `driftwatch/agents/prompts/narrator.md`)

- The "worth watching" paragraph is gone (Grace, 12:10 pm). The "use 'confident' only at 0.8 or
  more" sentence was in the same paragraph, so it is gone too, and Gemini now says "we are
  confident" for every Trusted gauge. To restore just the confidence rule, add back: *Use
  "confident" only when the confidence is 0.8 or more.* I also reverted the matching "worth
  watching" text in the fallback template, so the two narrators agree again.
- **Gemini got the sign wrong in 2 of the 4 Trusted narrations, so check them before using them
  on camera.**
  - Swannanoa measures +7 %: the river carries more than rated, so published flows are slightly
    low. Gemini wrote "published flows … running about 7% higher than the rating predicts" and
    called 7 % "close to" the gauge's normal 4.8 % scatter.
  - South Toe measures −1.2 %. Gemini wrote "running only 1.2% above the rating curve".
  - Eno (published flows 11 % higher than the field checks) and Watauga are worded correctly.
  - A rule in the prompt might help, something like: "say 'published flows are about X % too
    high/low', using the direction given". Better still, pass the narrator a precomputed
    `published_flows_are: "too high" | "too low"` field.
- Gemini tells managers to "ask the USGS to update the rating". The fallback template gives
  hydrographer-style actions ("apply a negative shift"). Gemini's version fits a utility manager better.

## Problems found and fixed during the run

- The OpenRouter skeptic crashed with "Event loop is closed" on 2 gauges when each site ran in
  its own event loop. The CLI now runs every site in one loop.
- Vertex returned 429 (rate limited) once per pass. Retries went from 1 to 3. The node fell back to
  the rules cleanly when it happened, and the run still finished.
- Gemini wrote "23.8/100" where the guard expected "24". The narrator now gets an exact score
  sentence to end on, and the guard accepts either form.
- On an early pass the LLM skeptic flip-flopped on Hepco (fill → debris → fill) and labeled both
  objections "sign mismatch" when the signs matched. It now sees its earlier objections and is told
  that choosing between fill, debris and vegetation is not an error. A code guard relabels a false
  "sign mismatch".

## How to reproduce

`make test` · `make demo` (fallback, offline) · `make run SITE=03455000 LLM=gemini` (needs
`.env` credentials) · replay a trace: `python -c "from driftwatch.agents.trace import replay;
[print(e.node, e.status) for e in replay('traces/<file>.json')]"`.
