"""End-to-end on the snapshot: the 'Done means' bands from CLAUDE.md, and the CLI output."""

import json

import pytest

from driftwatch import cli
from driftwatch.core.schemas import Report
from driftwatch.modules.rating_curve import report


@pytest.fixture(scope="module")
def reports():
    sites = ["03459500", "03455000", "03451000", "03463300", "02085000"]
    return {s: report.build_report(s) for s in sites}


@pytest.mark.parametrize("site", ["03459500", "03455000"])
def test_hero_gauges_are_stale_with_a_cause(reports, site):
    rep = reports[site]
    assert rep.trust.band == "Stale"
    assert rep.likely_cause and rep.narrative
    assert report.top_shift(rep.relationship.reference_end, rep.drift).direction == "negative"


def test_newport_cause_is_fill_and_hepco_flags_the_sign_mismatch(reports):
    assert reports["03455000"].likely_cause == "fill"
    hepco = reports["03459500"]
    assert hepco.likely_cause == "datum_change"
    assert "scour" in hepco.narrative and "opposite" in hepco.narrative


@pytest.mark.parametrize("site", ["03451000", "03463300", "02085000"])
def test_controls_are_trusted_with_no_invented_cause(reports, site):
    rep = reports[site]
    assert rep.trust.band == "Trusted"
    assert rep.likely_cause is None


def test_every_deduction_has_a_reason_with_a_number(reports):
    for rep in reports.values():
        assert len(rep.trust.deductions) == 5
        for d in rep.trust.deductions:
            assert any(ch.isdigit() for ch in d.reason), d


def test_cli_writes_report_json_and_prints_station_name(tmp_path, capsys):
    assert cli.main(["report", "--site", "03451000", "--out", str(tmp_path)]) == 0
    line = capsys.readouterr().out.strip()
    assert line.startswith("SWANNANOA RIVER AT BILTMORE, NC (03451000): Trusted")
    data = json.loads((tmp_path / "03451000.json").read_text(encoding="utf-8"))
    assert Report.model_validate(data).site_name == "SWANNANOA RIVER AT BILTMORE, NC"


def test_cli_refuses_live_source(capsys):
    assert cli.main(["report", "--site", "03451000", "--source", "live"]) == 2


def test_report_counts_invalid_domain_and_stays_finite():
    from datetime import timedelta

    from driftwatch.core.schemas import Measurement
    from driftwatch.modules.rating_curve import rating
    from tests.test_segmentation import _synthetic_ds

    ds = _synthetic_ds()
    e = rating.fit_rating(ds).e
    last = ds.measurements[-1].time
    low = Measurement(
        site="x",
        field_visit_id="low",
        time=last + timedelta(days=5),
        stage_ft=e - 0.05,
        discharge_cfs=3.0,
        rated="Good",
        weight=3.0,
    )
    ds = ds.model_copy(update={"measurements": [*ds.measurements, low]})
    rep = report.build_report("x", ds=ds)
    assert rep.drift.n_invalid_domain == 1
    assert "1 at or below rating zero" in report.summary_line(rep)
    assert all(d.points == d.points for d in rep.trust.deductions)  # no NaN points
