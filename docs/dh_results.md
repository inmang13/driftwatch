# DH results: two residual series, quality weighting, suggested shift, magnitude gate, reference mode

Run 2026-11-07 (round 2, 14:20) on the committed snapshot, branch `pi/dh-test`. `make test` 117 passed, `make demo` green offline.
Decisions and thresholds: docs/decision_log.md, entries "dh 1" to "dh 4" and "dh round 2".

**Bottom line:** in the default `fixed` mode nothing changes band. Hepco and Newport stay Stale with a post-Helene step that is larger in ft and concentrated at low flows; Asheville's step is larger in %. The magnitude gate cuts the Eno null's false alarms about 5-fold (56 % → 12 % at 80 visits). The new `auto` rule turns three healthy controls Stale (Swannanoa, Watauga, Eno), so it should not become the default as written (see Surprises 1).

## 1. Two residual series (fixed mode, gate on)

Shifts after the reference window, size = quality-weighted median after − before. Standardized step = |step| / robust σ of that series' reference residuals. "Low flow" = after the step, median |ft residual| in the lowest third of flows > in the top third. Gate = the smallest |size_pct| a change point needs to count as a shift. Holdout = searched measurements after the reference window.

| Site | Gauge | % series shifts | ft series shifts | % step (σ) | ft step (σ) | Larger | Low flow | Suggested shift ft (n) | Gate % | Holdout |
|---|---|---|---|---|---|---|---|---|---|---|
| 03459500 | Pigeon River near Hepco | 2024-12-17 −26 % / −0.33 ft | 2024-12-17 −26 % / −0.33 ft | 5.24 | 5.82 | ft | **True** | −0.335 (12) | 10.0 | 12 |
| 03455000 | French Broad near Newport | 2024-10-28 −42 % / −0.71 ft | 2024-10-28 −42 % / −0.71 ft | 8.13 | 11.26 | ft | **True** | −0.718 (14) | 10.0 | 14 |
| 03446000 | Mills River | none | none | — | — | — | False | −0.004 (164) | 10.0 | 16 |
| 03451500 | French Broad at Asheville | 2025-07-23 +46 % / +0.27 ft | 2025-07-23 +46 % / +0.27 ft | 9.77 | 5.13 | % | False | +0.265 (8) | 10.0 | 13 |
| 03451000 | Swannanoa at Biltmore | none | none | — | — | — | False | +0.006 (119) | 10.0 | 11 |
| 03463300 | South Toe near Celo | none | none | — | — | — | False | +0.000 (119) | 10.0 | 9 |
| 03479000 | Watauga near Sugar Grove | none | none | — | — | — | False | +0.005 (104) | 10.0 | 10 |
| 02085000 | Eno at Hillsborough | none | none | — | — | — | False | −0.001 (78) | 12.03 | 8 |

The gate removed Mills's 2019-05 −6 % step and Eno's 2022 blip (−17 / +11 %) from the % series, plus 1–3 in-window ft-series splits at each control. Because those merges lengthen the latest stable period, the suggested shift moved at Mills (n 63 → 164) and Eno (n 22 → 78); both stay near zero. No post-reference shift changed.

### Step 2 effect (quality weighting) vs the M1 numbers

| Gauge | Before | After |
|---|---|---|
| Hepco top shift | −28 % (−0.33 ft) | −26 % (−0.33 ft) |
| Newport top shift | −43 % (−0.72 ft) | −42 % (−0.71 ft) |
| Asheville top shift | +36 % (+0.27 ft) | +46 % (+0.27 ft) |
| Mills in-window blips 2016-02 (±51 %) | present | gone (they were Poor gaugings) |

## 3. Eno synthetic null, before and after the gate

The null adds N post-window visits to Eno. Each visit is a reference stage with a reference residual drawn at random, from the search series with Poor left out. No step is injected. Firing = any shift after the reference window. 50 seeds per row. Eno's gate is 12.03 % (1.5 × MdAPE 8.0 %).

| Post-window visits | No gate | Gate on |
|---|---|---|
| 20 | 18 % | 2 % |
| 40 | 40 % | 8 % |
| 80 | 56 % | 12 % |

The gate does not stop false alarms from growing with the number of looks (2 → 12 %), but it cuts them about 5-fold at every length. Eno has 8 searched post-window visits today.

## 4. Reference mode: fixed vs auto (round 2 rule)

Auto = the most recent stable period from the full-history search that ends at least 8 searched measurements before the latest one, and still has ≥ 15 measurements over ≥ 2 years. "(fixed kept)" = no period qualified.

| Site | Gauge | Fixed: band | Fixed: top shift | Fixed holdout | Auto window | Auto holdout | Auto: band | Auto: top shift | Differs |
|---|---|---|---|---|---|---|---|---|---|
| 03459500 | Pigeon River near Hepco | Stale 24 | 2024-12-17 −26 % (−0.33 ft) | 12 | 2004-09-08..2024-08-22 | 12 | Stale 24 | 2024-12-17 −25 % (−0.31 ft) | top shift (size) |
| 03455000 | French Broad near Newport | Stale 30 | 2024-10-28 −42 % (−0.71 ft) | 14 | 2004-09-09..2024-08-19 | 14 | Stale 30 | 2024-10-28 −43 % (−0.73 ft) | top shift (size) |
| 03446000 | Mills River | Watch 73 | none | 16 | 2012-01-01..2024-09-25 (fixed kept) | 16 | Watch 73 | none | — |
| 03451500 | French Broad at Asheville | Stale 46 | 2025-07-23 +46 % (+0.27 ft) | 13 | 2008-12-18..2025-06-03 | 8 | Stale 46 | 2025-07-23 +48 % (+0.27 ft) | top shift (size) |
| 03451000 | Swannanoa at Biltmore | Trusted 94 | none | 11 | 2004-06-09..2009-08-12 | 136 | **Stale 48** | 2009-10-01 +19 % (+0.09 ft) | **band**, top shift |
| 03463300 | South Toe near Celo | Trusted 95 | none | 9 | 2012-01-01..2024-09-25 (fixed kept) | 9 | Trusted 95 | none | — |
| 03479000 | Watauga near Sugar Grove | Trusted 95 | none | 10 | 1940-05-29..1984-04-12 | 282 | **Stale 30** | 1984-06-26 +33 % (+0.13 ft) | **band**, top shift |
| 02085000 | Eno at Hillsborough | Trusted 91 | none | 8 | 1999-10-12..2002-04-01 | 169 | **Stale 32** | 2009-06-04 +3,499 % (+0.11 ft) | **band**, top shift |

At Hepco, Newport and Asheville the shift date is the same in both modes; only its size moves by 1–2 points. The round-1 problem is gone: Newport's post-Helene period can no longer become the reference, because it runs to the latest gauging.

## Surprises

1. **The holdout rule breaks the healthy gauges.** When a gauge has been stable for a long time, its current state is one stable period that runs to the latest gauging, and the rule can never pick it. Auto then falls back to the period before it, which can be decades old: Swannanoa 2004–2009, Watauga 1940–1984, Eno 1999–2002. The result is a "shift" at the 2009 / 1984 / 2002 boundary and a Stale band. Eno's 1999–2002 rating extrapolates so badly at low flows that it reports steps of ±3,000 %. Mills and South Toe escape only because no older period qualifies, so they keep the fixed window. A likely fix: allow the latest period, but end the window 8 measurements before the latest gauging, so those 8 become the holdout. That is your call, so it is not built. The default stays `fixed`.
2. **The low-flow clue fires at both hero gauges and nowhere else** (unchanged from round 1). At Hepco and Newport the step is larger in ft and concentrated at low flows, the pattern of a change in the control's zero-flow height. Asheville shows the opposite: the whole curve slid.
3. **Gate merges reach the suggested shift.** Merging small in-window change points lengthens the latest stable period at Mills and Eno, so the suggested shift is now computed over 164 and 78 gaugings instead of 63 and 22. It is still about 0 ft at both.
4. **The ft series splits more than the % series inside the reference windows**, and the gate removes most of those splits. Robust σ in ft is tiny at low-stage gauges, so the ft lists are evidence to read beside the % series, not a second alarm.

## Not done / limits

- `reference_mode` is reachable only from `build_report(..., reference_mode="auto")`. The CLI and the API were outside the files this job could edit, so `make report` always runs fixed.
- Nothing in `driftwatch/agents/` or `driftwatch/api/` reads the new Report and DriftResult fields yet.
- `reports/*.json` were regenerated for all 8 gauges (fixed mode). They are in their own commits and can be dropped.
