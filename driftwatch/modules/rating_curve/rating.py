"""Base rating: weighted log-space power law Q = a (H - e)^b fitted on the reference window.

For a fixed offset e the fit is a weighted robust (Huber) regression of ln Q on ln(H - e); e is
found by a bounded 1-D search below the minimum reference stage. b and e then stay fixed: drift
is expressed as a sliding a, i.e. a % flow residual or an equivalent stage shift in ft.

Signs (CLAUDE.md): residual_pct = (Q_meas - Q_hat) / Q_hat * 100, so scour (more flow than the
rating at the same stage) is positive. stage_shift_ft = H_hat(Q_meas) - H_meas, the USGS
gage-height shift you would add to the stage reading; it carries the same sign as residual_pct.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares, minimize_scalar

from driftwatch.core.schemas import Dataset, Measurement, Relationship

E_GAP_FT = 0.01  # e must sit at least this far below the lowest reference stage
# Huber loss in ln Q: residuals beyond ~10 % flow error count linearly, not squared, so a few
# odd low-flow gaugings cannot bend the whole curve (Eno MdAPE 10.7 % -> 8.0 %).
HUBER_SCALE = 0.1


class FitError(ValueError):
    pass


def reference_measurements(ds: Dataset) -> list[Measurement]:
    return [
        m
        for m in ds.measurements
        if not m.excluded and ds.reference_start <= m.time.date() <= ds.reference_end
    ]


def _fit_given_e(h, q, w, e):
    """Weighted Huber regression of ln Q on ln(H - e). Returns (a, b, cost, log residuals)."""
    x = np.log(h - e)
    y = np.log(q)
    sw = np.sqrt(w)
    slope, intercept = np.polyfit(x, y, 1)
    res = least_squares(
        lambda p: sw * (y - p[0] - p[1] * x),
        [intercept, slope],
        loss="huber",
        f_scale=HUBER_SCALE,
    )
    lna, b = res.x
    return float(np.exp(lna)), float(b), float(res.cost), y - (lna + b * x)


def fit_power_law(h: np.ndarray, q: np.ndarray, w: np.ndarray) -> tuple[float, float, float, float]:
    """Return (a, b, e, rmse_log). e is searched in [h_min - span, h_min - E_GAP_FT]."""
    h, q, w = (np.asarray(v, dtype=float) for v in (h, q, w))
    if len(h) < 5:
        raise FitError(f"need at least 5 reference measurements, got {len(h)}")
    h_min = float(h.min())
    span = max(5.0, float(h.max() - h_min))
    hi = h_min - E_GAP_FT
    res = minimize_scalar(
        lambda e: _fit_given_e(h, q, w, e)[2],
        bounds=(h_min - span, hi),
        method="bounded",
        options={"xatol": 1e-4},
    )
    e = float(min(res.x, hi))
    a, b, _, resid = _fit_given_e(h, q, w, e)
    rmse = float(np.sqrt(np.average(resid**2, weights=w)))
    return a, b, e, rmse


def fit_rating(ds: Dataset) -> Relationship:
    ref = reference_measurements(ds)
    a, b, e, rmse = fit_power_law(
        np.array([m.stage_ft for m in ref]),
        np.array([m.discharge_cfs for m in ref]),
        np.array([m.weight for m in ref]),
    )
    return Relationship(
        a=a,
        b=b,
        e=e,
        reference_start=ds.reference_start,
        reference_end=ds.reference_end,
        n=len(ref),
        rmse_log=rmse,
    )


def predict_q(rel: Relationship, h):
    """Rated discharge at stage h. Stages at or below e give 0."""
    d = np.clip(np.asarray(h, dtype=float) - rel.e, 0.0, None)
    return rel.a * d**rel.b


def predict_h(rel: Relationship, q):
    """Stage the base rating needs to carry discharge q."""
    return rel.e + (np.asarray(q, dtype=float) / rel.a) ** (1.0 / rel.b)


def residual_pct(rel: Relationship, h, q):
    qhat = predict_q(rel, h)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(qhat > 0, (np.asarray(q, dtype=float) - qhat) / qhat * 100.0, np.nan)


def stage_shift_ft(rel: Relationship, h, q):
    """USGS-style gage-height shift: positive when the channel carries more flow (scour)."""
    return predict_h(rel, q) - np.asarray(h, dtype=float)


def residual_table(rel: Relationship, ms: list[Measurement]) -> list[dict]:
    """Per-measurement residuals, in time order, for plots and the drift test."""
    h = np.array([m.stage_ft for m in ms])
    q = np.array([m.discharge_cfs for m in ms])
    r = residual_pct(rel, h, q) if ms else np.array([])
    s = stage_shift_ft(rel, h, q) if ms else np.array([])
    rows = []
    for m, ri, si in zip(ms, r, s, strict=True):
        rows.append(
            {
                "time": m.time,
                "stage_ft": m.stage_ft,
                "discharge_cfs": m.discharge_cfs,
                "residual_pct": float(ri),
                "stage_shift_ft": float(si),
                "rated": m.rated,
                "weight": m.weight,
                "control_condition": m.control_condition,
                "excluded": m.excluded,
            }
        )
    return rows


def mdape(rel: Relationship, ms: list[Measurement]) -> float:
    r = residual_pct(rel, [m.stage_ft for m in ms], [m.discharge_cfs for m in ms])
    return float(np.nanmedian(np.abs(r)))
