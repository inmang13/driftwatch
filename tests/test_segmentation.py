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
