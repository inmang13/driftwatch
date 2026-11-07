# DH results: two residual series, quality weighting, suggested shift, reference mode

Run 2026-11-07 on the committed snapshot, branch `pi/dh-test`. `make test` 113 passed, `make demo` green offline.
Decisions and thresholds: docs/decision_log.md, entries "dh 1" to "dh 4".

**Bottom line:** no gauge changes band in either mode. Hepco and Newport stay Stale, and their post-Helene step is larger in ft than in % and concentrated at low flows, which points to a change in the control's zero-flow height. Asheville's step is larger in %. `auto` reference mode agrees with `fixed` today, but only by a margin of one gauging at Newport (see Surprises).

## 1. Two residual series (fixed mode)

Shifts after the reference window, size = quality-weighted median after − before (step 2). Standardized step = |step| / robust σ of that series' reference residuals. "Low flow" = after the step, median |ft residual| in the lowest third of flows > in the top third.

| Site | Gauge | % series shifts | ft series shifts | % step (σ) | ft step (σ) | Larger | Low flow | Suggested shift ft (n) | Poor left out of search |
|---|---|---|---|---|---|---|---|---|---|
| 03459500 | Pigeon River near Hepco | 2024-12-17 −26 % / −0.33 ft | 2024-12-17 −26 % / −0.33 ft | 5.24 | 5.82 | ft | **True** | −0.335 (12) | 11 |
| 03455000 | French Broad near Newport | 2024-10-28 −42 % / −0.71 ft | 2024-10-28 −42 % / −0.71 ft | 8.13 | 11.26 | ft | **True** | −0.718 (14) | 4 |
| 03446000 | Mills River | none | none | — | — | — | False | −0.026 (63) | 15 |
| 03451500 | French Broad at Asheville | 2025-07-23 +46 % / +0.27 ft | 2025-07-23 +46 % / +0.27 ft | 9.77 | 5.13 | % | False | +0.265 (8) | 8 |
| 03451000 | Swannanoa at Biltmore | none | none | — | — | — | False | +0.006 (119) | 8 |
| 03463300 | South Toe near Celo | none | none | — | — | — | False | +0.000 (119) | 4 |
| 03479000 | Watauga near Sugar Grove | none | none | — | — | — | False | +0.005 (104) | 10 |
| 02085000 | Eno at Hillsborough | none | none | — | — | — | False | −0.013 (22) | 19 |

After the reference window the two series find the same shift dates at every gauge. Inside the reference windows they differ: the ft series splits Swannanoa (2018), South Toe (2017), Watauga (2018–19), Mills (2018-10, where the % series splits 2019-05) and Eno (2015, 2016, 2022-03, where the % series has a blip at 2022-09..11). Those splits are older than the windows' ends, so they affect neither the band nor the top shift. The suggested shift is provisional ("a hydrographer confirms") and uses USGS sign: it is the amount to add to the gage reading.

### Step 2 effect (quality weighting) vs the M1 numbers

| Gauge | Before | After |
|---|---|---|
| Hepco top shift | −28 % (−0.33 ft) | −26 % (−0.33 ft) |
| Newport top shift | −43 % (−0.72 ft) | −42 % (−0.71 ft) |
| Asheville top shift | +36 % (+0.27 ft) | +46 % (+0.27 ft) |
| Mills in-window blips 2016-02 (±51 %) | present | gone (they were Poor gaugings) |
| Eno in-window blip 2022-09 | −44 % | −17 % |

Bands and scores are unchanged at all 8. The fallback agent verdicts are unchanged too: Hepco fill 0.60 with 1 objection, Newport fill 0.44, Asheville scour 0.50.

## 4. Reference mode: fixed vs auto

| Site | Gauge | Fixed: band | Fixed: top shift | Auto window | Auto: band | Auto: top shift | Differs |
|---|---|---|---|---|---|---|---|
| 03459500 | Pigeon River near Hepco | Stale 24 | 2024-12-17 −26 % (−0.33 ft) | 2012-01-13..2024-08-22 | Stale 24 | 2024-12-17 −26 % (−0.33 ft) | — |
| 03455000 | French Broad near Newport | Stale 30 | 2024-10-28 −42 % (−0.71 ft) | 2011-08-05..2024-08-19 | Stale 30 | 2024-10-28 −42 % (−0.71 ft) | — |
| 03446000 | Mills River | Watch 73 | none | 2013-09-05..2024-09-06 | Watch 76 | none | — |
| 03451500 | French Broad at Asheville | Stale 46 | 2025-07-23 +46 % (+0.27 ft) | 2008-12-18..2025-06-03 | Stale 46 | 2025-07-23 +48 % (+0.27 ft) | **top shift** |
| 03451000 | Swannanoa at Biltmore | Trusted 94 | none | 2009-10-01..2026-10-02 | Trusted 93 | none | — |
| 03463300 | South Toe near Celo | Trusted 95 | none | 1980-06-19..2026-10-14 | Trusted 95 | none | — |
| 03479000 | Watauga near Sugar Grove | Trusted 95 | none | 1999-02-03..2026-10-14 | Trusted 95 | none | — |
| 02085000 | Eno at Hillsborough | Trusted 91 | none | 2022-11-28..2026-10-15 | Trusted 94 | none | — |

Only one row differs: Asheville's top shift moves by 2 points. The scores move a little (Mills +3, Eno +3, Swannanoa −1) because the base rating is refitted on a different window.

## Surprises

1. **Auto mode keeps Newport Stale by a margin of one gauging.** Newport's post-Helene stable period has 14 gaugings over 1.97 years, against a requirement of 15 over 2 years. The next gauging will make it qualify. From then on, auto adopts the post-Helene channel as the reference, the shift drops out of the test, and Newport scores as healthy against its own new state. Hepco is at 12 gaugings over 1.63 years: it needs 3 more gaugings and a period that runs past 2026-12-17. Asheville is at 8 over 1.23 years. Read this way, auto answers "is the channel consistent with itself lately", not "has it moved off the published rating". The default stays `fixed`; whether auto should be capped at the fixed reference end (or the Helene date) is Grace's call.
2. **On the controls the auto window runs to the latest gauging**, so nothing after it is tested. South Toe's window goes back to 1980. For these gauges the Trusted band in auto mode holds by construction, so it is not evidence. `reference_note` says so in the report.
3. **The low-flow clue fires at both hero gauges and nowhere else.** At Hepco and Newport the ft step is the larger one and it is concentrated at low flows: the pattern of a change in the control's zero-flow height. Asheville's +46 % is the opposite pattern, larger in % and not low-flow concentrated, so the whole curve slid. This is a deterministic clue for the agents, not a cause.
4. **The false-alarm rate on the Eno null rose a little at long series.** With Poor gaugings left out of the search (step 2), the 50-seed synthetic null fires 4 / 18 / 40 % of the time at 10 / 20 / 40 post-window visits. It was about 4 / 14–26 / 34 %. Eno has 11 post-window visits today. Not retuned.
5. **Inside the reference windows the ft series splits where the % series does not** (Swannanoa, South Toe, Watauga, and three times at Eno). Robust σ in ft is tiny at low-stage gauges. The ft lists are evidence to read alongside the % series, not a second alarm.

## Not done / limits

- `reference_mode` is reachable from `build_report(..., reference_mode="auto")` only. The CLI (`driftwatch/cli.py`) and the API were outside the files this job could edit, so `make report` always runs fixed.
- New Report and DriftResult fields are additive. Nothing in `driftwatch/agents/` or `driftwatch/api/` reads them yet.
- `reports/*.json` were regenerated for all 8 gauges (fixed mode) so they carry the new fields. `make demo` rewrites two of them anyway. They are in their own commit and can be dropped.
