# M2 results: what the agent team says about the 8 gauges

*Branch `m2-agents`, 2026-11-07 around 11:45 am. These are the Gemini runs, with traces in `traces/`. Ranker and
narrator ran on Vertex `gemini-3.8-flash`. The skeptic ran on OpenRouter `openai/gpt-5.4-mini`.
Every LLM call succeeded and no node fell back to the rules. The fallback runs (`LLM=fallback`)
are listed for comparison; `make test` and `make demo` use those.*

## Decision for Grace: where does the "skeptic objects" moment come from?

**With Gemini, the skeptic objects on no gauge, Hepco included.** The Gemini ranker sees the
−33 % residual and rules scour out by itself ("field notes mention scour, but the persistent −33 %
residual … directly contradicts scour"). It ranks fill first at 45 %, with datum change second at 30 %. The
skeptic then checks the channel numbers and agrees.

**With the fallback rules, the skeptic objects on Hepco.** The rule-based ranker puts datum change
first, because the scour note contradicts the sign. The skeptic then objects on the channel
evidence and the ranker switches to fill. That run is deterministic.

The options for the video and demo:
1. **Replay the fallback Hepco trace** for the skeptic moment. It is honest, since it is a real
   run, but it shows the rules and not Gemini.
2. **Pitch Hepco as "the AI didn't fall for the scour note"**: Gemini rules out scour and the
   skeptic confirms with the channel numbers. No objection is shown.
3. Make the skeptic tougher in `driftwatch/agents/prompts/skeptic.md`. I would not do this just to
   get an objection on camera. That is tuning to the demo.

My recommendation: **option 2 for the live run, with option 1 as the replay for the "skeptic"
beat.** In the voice-over, say which one is which.

How I got here: on the first Gemini pass the ranker prompt quoted Hepco's exact case ("a scour
note with a negative residual does not support scour"), and the ranker could also see the channel
numbers. I removed both, so the channel check now belongs to the skeptic, as it does in the
fallback. Gemini still picks fill. The result holds without the hint.

## Gemini run, per gauge

Key: **Final cause** is the team's answer after the skeptic, and **conf.** is the ranker's
confidence in it (0–1). **Objected?** says whether the skeptic sent the ranker back. **Tokens** are
input + output across all LLM calls in the run. **Wall** is seconds for the whole run, including
the M1 engine.

| Site | Gauge | Band (score) | Final cause | Conf. | Objected? | Tokens | Wall |
|---|---|---|---|---|---|---|---|
| 03459500 | Pigeon R near Hepco | Stale (24) | fill | 0.45 | no | 5,525 + 744 | 38.6 s |
| 03455000 | French Broad near Newport | Stale (30) | fill | 0.82 | no | 6,151 + 790 | 24.7 s |
| 03446000 | Mills R | Watch (73) | debris | 0.55 | no | 5,730 + 650 | 27.7 s |
| 03451500 | French Broad at Asheville | Stale (46) | scour | 0.70 | no | 5,666 + 674 | 39.6 s |
| 03451000 | Swannanoa at Biltmore | Trusted (94) | none (straight to narrator) | — | — | 885 + 113 | 17.2 s |
| 03463300 | South Toe near Celo | Trusted (95) | none | — | — | 886 + 107 | 6.6 s |
| 03479000 | Watauga near Sugar Grove | Trusted (95) | none | — | — | 882 + 115 | 6.5 s |
| 02085000 | Eno at Hillsborough | Trusted (91) | none | — | — | 885 + 118 | 9.5 s |

All 8 together: about 27,000 input and 3,300 output tokens, a little under 3 minutes end to end.
Gemini latency swings a lot: the same ranker call took 11 s on one run and 71 s on another.

**What the skeptic said** (it accepted every time):
- **Hepco:** fill fits the negative sign. Speed fell 22 % while area changed only 11 %, which is
  "consistent with backwater/fill rather than scour or a pure datum issue."
- **Newport:** area rose 25 % while speed fell 58 %, "a strong backwater/fill signal rather
  than a datum change."
- **Asheville:** scour fits the +41 % residual. Area +8 % and speed +2 % show no backwater, so
  there is nothing in the geometry to object to.
- **Mills:** debris fits. It names fill as a plausible alternative.

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

- Every Gemini narration stayed within 120 words, ended with the score line, and matched the
  ranker's confidence ("confident" appears only for Newport at 0.82).
- After my prompt tweak, Eno (−11 %, normal scatter 8 %) and Swannanoa (+7 %, normal scatter 5 %)
  read "worth watching" rather than "nothing is wrong", even though both are Trusted. Decide whether you
  want that. To revert, delete the last paragraph of `narrator.md`.
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
