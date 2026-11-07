"""Recursive segmentation: synthetic step, and the three calibration gauges from the plan."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from driftwatch.core.schemas import Dataset, Measurement
from driftwatch.modules.rating_curve import pairing, rating, segmentation

HELENE = datetime(2024, 9, 26, tzinfo=UTC)


def _post_helene_shifts(site):
    ds = pairing.load_dataset(site)
    drift = segmentation.drift_test(ds, rating.fit_rating(ds))
    return drift, [s for s in drift.shifts if s.time >= HELENE]


def test_change_points_find_a_clean_step_and_ignore_noise():
    rng = np.random.default_rng(1)
    quiet = rng.normal(0, 1, 80)
    assert segmentation.change_points(quiet) == []
    step = np.concatenate([rng.normal(0, 1, 60), rng.normal(-8, 1, 20)])
    assert segmentation.change_points(step) == [60]


def test_synthetic_fill_shift_is_negative_with_size():
    rng = np.random.default_rng(2)
    t0 = datetime(2012, 1, 1, tzinfo=UTC)
    ms = []
    for i in range(100):
        h = float(rng.uniform(1.5, 8.0))
        factor = 0.7 if i >= 80 else 1.0  # 30 % less flow at the same stage after point 80
        q = 40.0 * (h - 0.5) ** 1.7 * factor * float(np.exp(rng.normal(0, 0.03)))
        ms.append(
            Measurement(
                site="x",
                field_visit_id=str(i),
                time=t0 + timedelta(days=60 * i),
                stage_ft=h,
                discharge_cfs=q,
                rated="Good",
                weight=3.0,
            )
        )
    ds = Dataset(
        site="x",
        source="snapshot",
        reference_start=t0.date(),
        reference_end=ms[79].time.date(),
        measurements=ms,
    )
    drift = segmentation.drift_test(ds, rating.fit_rating(ds))
    assert len(drift.shifts) == 1
    s = drift.shifts[0]
    assert s.time == ms[80].time
    assert s.direction == "negative"
    assert s.size_pct == pytest.approx(-30, abs=5)
    assert s.size_ft < 0
    assert s.n_after == 20 and s.confidence > 0.99
    assert [p.n for p in drift.stable_periods] == [80, 20]


@pytest.mark.parametrize("site", ["02085000", "03451000"])
def test_controls_have_no_shift_after_helene(site):
    _, post = _post_helene_shifts(site)
    assert post == []


def test_newport_shifts_negative_after_helene():
    drift, post = _post_helene_shifts("03455000")
    assert len(post) == 1
    assert post[0].direction == "negative" and post[0].size_pct < -20
    assert drift.n_excluded >= 1  # the Sept 27-28 Poor flood gaugings are held out


def _synthetic_ds(n_ref=80, n_post=20, factor=1.0, seed=3):
    rng = np.random.default_rng(seed)
    t0 = datetime(2012, 1, 1, tzinfo=UTC)
    ms = []
    for i in range(n_ref + n_post):
        h = float(rng.uniform(1.5, 8.0))
        f = factor if i >= n_ref else 1.0
        q = 40.0 * (h - 0.5) ** 1.7 * f * float(np.exp(rng.normal(0, 0.03)))
        ms.append(
            Measurement(
                site="x",
                field_visit_id=str(i),
                time=t0 + timedelta(days=60 * i),
                stage_ft=h,
                discharge_cfs=q,
                rated="Good",
                weight=3.0,
            )
        )
    return Dataset(
        site="x",
        source="snapshot",
        fetched_at=ms[-1].time + timedelta(days=30),
        reference_start=t0.date(),
        reference_end=ms[n_ref - 1].time.date(),
        measurements=ms,
    )


def test_stage_at_or_below_e_is_invalid_domain_left_out_and_counted():
    ds = _synthetic_ds()
    rel = rating.fit_rating(ds)
    last = ds.measurements[-1].time
    low = [
        Measurement(
            site="x",
            field_visit_id=f"low{k}",
            time=last + timedelta(days=10 * (k + 1)),
            stage_ft=rel.e - 0.1 * k,  # at e, then below it
            discharge_cfs=3.0,
            rated="Good",
            weight=3.0,
        )
        for k in range(3)
    ]
    ds = ds.model_copy(update={"measurements": ds.measurements + low})
    drift = segmentation.drift_test(ds, rel)
    assert drift.n_invalid_domain == 3
    assert drift.n_tested == 100
    assert all(np.isfinite(s.size_pct) and np.isfinite(s.size_ft) for s in drift.shifts)
    assert all(np.isfinite(p.median_residual_pct) for p in drift.stable_periods)
    rows = rating.residual_table(rel, ds.measurements)
    assert [r["invalid_domain"] for r in rows[-3:]] == [True, True, True]
    assert not any(r["invalid_domain"] for r in rows[:-3])
