# DriftWatch eval report

Generated 2026-11-07 23:51 UTC by `make evals` on thoth (aarch64). Cases: `evals/cases.yaml`; runner: `evals/run_evals.py`.

**LLM=fallback: 10/13 pass**, 71 s total. Each cell gives pass/fail, the case's wall time, and what was checked.

Cases 4 and 9-12 never call an LLM (deterministic report, synthetic data, replay), so their result is the same in every column. The LLM=gemini column is filled by `make evals LLM=gemini` on the laptop (needs the Vertex credentials).

| # | Case | LLM=fallback | LLM=gemini |
|---|---|---|---|
| 1 | Newport - Stale, fill, cites the field note | PASS (3.5 s) band Stale (want Stale); cause fill (0.44); 'Fill control changed' cited as fill evidence | [run on laptop] |
| 2 | Hepco - Stale, Disagreement against the scour note | PASS (6.0 s) band Stale (want Stale); Disagreement yes; field note 'Scour control changed' (2024-12-17); best guess fill | [run on laptop] |
| 3 | Asheville - Stale, cause open, no mechanism named | PASS (7.3 s) band Stale (want Stale); cause_status open; no mechanism words | [run on laptop] |
| 4 | Mills - Watch, significant lower trend, no step | PASS (29.9 s) band Watch (want Watch); 0 shift(s) in the whole series; trend -0.84 %/yr, p 3.9e-13, CI -1.10..-0.60, significant=True | [run on laptop] |
| 5 | Swannanoa - Trusted, no cause | PASS (4.2 s) band Trusted (want Trusted); no cause named | [run on laptop] |
| 6 | South Toe - Trusted, no cause | PASS (3.9 s) band Trusted (want Trusted); no cause named | [run on laptop] |
| 7 | Watauga - Trusted, no cause | PASS (3.4 s) band Trusted (want Trusted); no cause named | [run on laptop] |
| 8 | Eno - Trusted, no cause | PASS (2.1 s) band Trusted (want Trusted); no cause named | [run on laptop] |
| 9 | Eno + synthetic +25 % step at 2025-07-01 - fires | **FAIL** (1.2 s) no positive shift near 2025-07-01; shifts: 2022-09-06 -17 %, 2022-11-28 +24 % | [run on laptop] |
| 10 | Eno + synthetic -1.5 %/yr slope - trend fires, no step | **FAIL** (1.5 s) 1 shift(s) in the whole series; trend -1.41 %/yr, p 0.54, CI -4.99..+8.21, significant=False | [run on laptop] |
| 11 | Eno flat (resampled reference residuals, seed 0) - 0 shifts | PASS (5.4 s) 0 shift(s) in the whole series | [run on laptop] |
| 12 | Replay determinism | PASS (0.4 s) two fallback runs identical; 03459500-20261107T180218430129Z.json: 20 events replay identically twice | [run on laptop] |
| 13 | Swannanoa + synthetic +25 % step at 2025-01-01 - fires | **FAIL** (2.7 s) no positive shift near 2025-01-01; shifts: 2025-06-11 +31 % | [run on laptop] |

## Why the failures fail

- **9. Eno + synthetic +25 % step at 2025-07-01 - fires:** Eno's own recent gaugings already sit about 10 % below the rating, so the +25 % step lands them only about +10-15 % above it, and there are 8 searched gaugings after 2025-07-01. At penalty 50 and Eno's scatter, 8 points at that size don't pay for a change point (no shift at 2025-07 even with the gate off). The search splits Eno's 2022 blip instead. Gauge stays Trusted.
- **10. Eno + synthetic -1.5 %/yr slope - trend fires, no step:** The trend method does see the slope: fitted over the whole uncut series it gives -2.5 %/yr, p 2e-7, significant (the injected -1.5 plus Eno's own -0.95). But the slope pushes Eno's 2022-09 blip over the shift gate, so the change-point search reports a -16 % step there; the trend then only fits the 4 years after it and comes out non-significant. A slow slide gets read as a step.
- **13. Swannanoa + synthetic +25 % step at 2025-01-01 - fires:** It does fire, but dated 2025-06-11 (+31 %), 161 days after the step. The only gauging in between is 2025-02-10 (Fair), which read -13 % before the step, so +25 % lifts it to only about +8 %, inside normal scatter; the search starts the new segment at the next gauging. Swannanoa is gauged every few months, so 120 days is tighter than its gaps.

## How the synthetic cases are built

- **Step:** every Eno gauging on or after 2025-07-01 has its discharge multiplied by 1.25. The
  check accepts a positive shift dated 2025-07-01 .. +120 days. (Eno's reference window ends
  2025-07-06; no searched gauging falls between the two dates, so none of the step is in the fit.)
- **Slope:** every Eno gauging from the reference start (2015-01-01) on has its discharge
  multiplied by 1 - 0.015 x years since then. It adds to Eno's own slope (-0.95 %/yr, not
  significant on the real data).
- **Flat:** every Eno gauging from the reference start on gets Q = rating(H) x a reference
  residual drawn with replacement (seed 0, fixed before running). Same dates and stages, no
  step, no slope. One seed is a smoke test; the decision log records the change-point search's
  false-alarm rate across seeds.
- **Replay:** two fallback runs on Hepco must agree on the final call, rankings, objections,
  verdict and narration; Hepco's saved Replay trace (`traces/replay_defaults.json`) must replay
  the same events twice, in seq order.
