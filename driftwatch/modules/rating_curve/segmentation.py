"""Darienzo-style recursive segmentation of the rating residual series.

Series: every non-excluded measurement from the start of the reference window onward, in time
order. The change-point search runs on ln(Q_meas / Q_hat), standardized by the robust spread
(1.4826 x MAD) of the reference-window residuals, so one penalty means the same thing at a
quiet gauge and a noisy one. PELT (l2 cost, min_size 6) splits the series; each piece is searched
again until no piece splits. Sizes are reported in plain % flow and ft (see rating.py signs).

A shift's size is the step between the median residual of the segment before and the segment
after it. confidence = 1 - Mann-Whitney p-value between those two segments.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import ruptures as rpt
from scipy.stats import mannwhitneyu

from driftwatch.core.schemas import (
    Dataset,
    DriftResult,
    Measurement,
    Relationship,
    Shift,
    StablePeriod,
)
from driftwatch.modules.rating_curve import rating

# Chosen from a fixed list (decision log 2026-11-06): any value in 25..150 keeps Eno and
# Swannanoa quiet after Helene and fires on Newport; 50 sits well inside that window.
PENALTY = 50.0
MIN_SIZE = 6


def tested_measurements(ds: Dataset) -> list[Measurement]:
    return [m for m in ds.measurements if not m.excluded and m.time.date() >= ds.reference_start]


def change_points(z: np.ndarray, penalty: float = PENALTY, min_size: int = MIN_SIZE) -> list[int]:
    """Indices where a new segment starts, found by recursive PELT."""
    n = len(z)
    if n < 2 * min_size:
        return []
    algo = rpt.Pelt(model="l2", min_size=min_size, jump=1).fit(z.reshape(-1, 1))
    inner = algo.predict(pen=penalty)[:-1]
    if not inner:
        return []
    edges = [0, *inner, n]
    found: set[int] = set(inner)
    for lo, hi in pairwise(edges):
        found.update(lo + c for c in change_points(z[lo:hi], penalty, min_size))
    return sorted(found)


def _robust_sigma(x: np.ndarray) -> float:
    s = 1.4826 * float(np.median(np.abs(x - np.median(x)))) if len(x) else 0.0
    return s if s > 0 else (float(np.std(x)) or 1.0)


def drift_test(ds: Dataset, rel: Relationship, penalty: float = PENALTY) -> DriftResult:
    ms = tested_measurements(ds)
    n_excluded = sum(1 for m in ds.measurements if m.excluded)
    if not ms:
        return DriftResult(site=ds.site, n_excluded=n_excluded, penalty=penalty)

    h = np.array([m.stage_ft for m in ms])
    q = np.array([m.discharge_cfs for m in ms])
    log_r = np.log(q / rating.predict_q(rel, h))
    pct = rating.residual_pct(rel, h, q)
    ft = rating.stage_shift_ft(rel, h, q)

    in_ref = np.array([m.time.date() <= ds.reference_end for m in ms])
    ref = log_r[in_ref] if in_ref.any() else log_r
    z = (log_r - np.median(ref)) / _robust_sigma(ref)

    cps = change_points(z, penalty)
    edges = [0, *cps, len(ms)]
    segments = list(pairwise(edges))

    stable = [
        StablePeriod(
            start=ms[lo].time,
            end=ms[hi - 1].time,
            n=hi - lo,
            median_residual_pct=round(float(np.median(pct[lo:hi])), 2),
        )
        for lo, hi in segments
    ]
    shifts = []
    for (lo, mid), (_, hi) in pairwise(segments):
        size_pct = float(np.median(pct[mid:hi]) - np.median(pct[lo:mid]))
        size_ft = float(np.median(ft[mid:hi]) - np.median(ft[lo:mid]))
        p = mannwhitneyu(log_r[lo:mid], log_r[mid:hi]).pvalue
        shifts.append(
            Shift(
                time=ms[mid].time,
                size_pct=round(size_pct, 2),
                size_ft=round(size_ft, 3),
                direction="positive" if size_pct > 0 else "negative",
                n_after=hi - mid,
                confidence=round(float(np.clip(1.0 - p, 0.0, 1.0)), 4),
            )
        )
    return DriftResult(
        site=ds.site,
        stable_periods=stable,
        shifts=shifts,
        n_tested=len(ms),
        n_excluded=n_excluded,
        penalty=penalty,
    )
