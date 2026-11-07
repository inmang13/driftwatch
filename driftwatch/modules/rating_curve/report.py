"""Snapshot -> Report for one gauge: pairing, base rating, drift test, trust score, likely cause.

The likely cause here is the deterministic triage call (no LLM). The agents in M2 refine it.

Two sets of measurements, on purpose:
- visits (`visits_since_reference`): every paired gauging from the reference start on, including
  the Helene-excluded flood gaugings and invalid_domain ones. A visit is a visit: these drive
  staleness, the 12-month data count, and field-note flags / note-based causes.
- tested (`segmentation.tested_measurements`): the drift-test series. Helene-excluded and
  invalid_domain gaugings stay out; it drives the fit, the drift test, the recent residual and
  the recent quality grade.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np

from driftwatch.core import trust
from driftwatch.core.schemas import Dataset, DriftResult, Relationship, Report, Shift
from driftwatch.modules.rating_curve import causes, pairing, rating, segmentation

RECENT_N = 8
NOTE_SEVERITY_POINTS = {"light": 3.0, "moderate": 8.0, "heavy": 12.0}
CONTROL_CHANGED_POINTS = 15.0


def visits_since_reference(ds: Dataset):
    """Every paired gauging from the reference start on, excluded or not, in time order."""
    return [m for m in ds.measurements if m.time.date() >= ds.reference_start]


def recent_measurements(ds: Dataset, rel: Relationship, drift: DriftResult):
    """Newest RECENT_N tested measurements inside the latest stable period."""
    ms = segmentation.tested_measurements(ds, rel)
    if drift.stable_periods:
        start = drift.stable_periods[-1].start
        ms = [m for m in ms if m.time >= start]
    return ms[-RECENT_N:]


DASHES = str.maketrans({"–": "-", "—": "-", "−": "-"})  # en, em, minus sign


def note_severity_points(note: str) -> float:
    """Points for a transient note like 'Debris - Moderate'. En/em dashes count as hyphens;
    an unreadable severity falls back to light."""
    sev = note.translate(DASHES).split("-")[-1].strip().lower()
    return NOTE_SEVERITY_POINTS.get(sev, NOTE_SEVERITY_POINTS["light"])


def field_flags(ds: Dataset) -> list[tuple[str, float]]:
    """Open field-note flags: control changes since the reference window, transients only if on
    the latest visit (a later visit without them means they cleared)."""
    visits = visits_since_reference(ds)
    flags: dict[str, float] = {}
    for m in visits:
        note = m.control_condition or ""
        if m.time.date() > ds.reference_end and "control changed" in note.lower():
            flags[note] = CONTROL_CHANGED_POINTS
    if visits:
        note = visits[-1].control_condition or ""
        cause = causes.cause_for_note(note)
        if cause and cause.transient:
            flags[note] = note_severity_points(note)
    return list(flags.items())


def trust_inputs(ds: Dataset, rel: Relationship, drift: DriftResult, as_of: datetime):
    recent = recent_measurements(ds, rel, drift)
    visits = visits_since_reference(ds)
    h = [m.stage_ft for m in recent]
    q = [m.discharge_cfs for m in recent]
    return trust.TrustInputs(
        recent_residual_pct=[float(x) for x in rating.residual_pct(rel, h, q)] if recent else [],
        normal_scatter_pct=rating.mdape(rel, rating.reference_measurements(ds)),
        days_since_last=(as_of - visits[-1].time).total_seconds() / 86400 if visits else None,
        recent_rated=[m.rated for m in recent],
        field_flags=field_flags(ds),
        n_last_year=sum(1 for m in visits if m.time > as_of - timedelta(days=365)),
    )


def top_shift(reference_end: date, drift: DriftResult) -> Shift | None:
    """Largest shift after the reference window (older ones are already in the base rating)."""
    post = [s for s in drift.shifts if s.time.date() > reference_end]
    return max(post, key=lambda s: abs(s.size_pct)) if post else None


def likely_cause(
    ds: Dataset, inputs: trust.TrustInputs, band: str
) -> tuple[str | None, str | None]:
    """(cause key, one-sentence why). None when the gauge is Trusted or the error is in the noise.

    Rules: the direction is the sign of the recent median residual. A field note since the
    reference window whose cause matches that sign wins (persistent before transient). A
    control-changed note that contradicts the sign points to a datum change / rebuild (a
    contradicting debris/vegetation note is just ignored). Otherwise -> the persistent cause for
    that sign (scour or fill), to be checked against channel evidence by the agents.
    """
    if band == "Trusted" or not inputs.recent_residual_pct:
        return None, None
    med = float(np.median(inputs.recent_residual_pct))
    if abs(med) <= inputs.normal_scatter_pct:
        return None, None
    if inputs.n_last_year < trust.DATA_TARGET_PER_YEAR:
        return "insufficient_data", "Too few recent measurements to name a cause."
    direction = "positive" if med > 0 else "negative"
    noted = []
    for m in visits_since_reference(ds):
        c = causes.cause_for_note(m.control_condition)
        if c and m.time.date() > ds.reference_end and c not in noted:
            noted.append(c)
    agree = sorted(
        (c for c in noted if causes.sign_agrees(c, direction)), key=lambda c: c.transient
    )
    word = "more" if med > 0 else "less"
    if agree:
        c = agree[0]
        return c.key, (
            f"Field note says {c.label.lower()}, and the gauge reads {abs(med):.0f} % {word} "
            f"water than rated, which is the direction {c.label.lower()} produces."
        )
    contradicting = [c for c in noted if not c.transient]
    if contradicting:
        names = ", ".join(c.label.lower() for c in contradicting)
        return "datum_change", (
            f"Field notes say {names}, but the gauge reads {abs(med):.0f} % {word} water than "
            f"rated, the opposite of what that would do; a datum change or gauge rebuild (or "
            f"fill) fits the sign better. Check the gauge history."
        )
    c = causes.get_cause("scour" if direction == "positive" else "fill")
    return c.key, (
        f"No field note explains it; {abs(med):.0f} % {word} water than rated is the direction "
        f"{c.label.lower()} produces. Check channel area for confirmation."
    )


def build_report(site: str, source: str = "snapshot", ds: Dataset | None = None) -> Report:
    ds = ds or pairing.load_dataset(site, source)
    rel = rating.fit_rating(ds)
    drift = segmentation.drift_test(ds, rel)
    as_of = ds.fetched_at or datetime.now(UTC)
    inputs = trust_inputs(ds, rel, drift, as_of)
    ts = trust.score(inputs)
    cause, why = likely_cause(ds, inputs, ts.band)
    return Report(
        site=ds.site,
        site_name=ds.site_name,
        generated_at=datetime.now(UTC),
        source=ds.source,
        relationship=rel,
        drift=drift,
        trust=ts,
        likely_cause=cause,
        narrative=why,
    )


def summary_line(report: Report) -> str:
    """Station name, band, score, top shift since the reference window."""
    top = top_shift(report.relationship.reference_end, report.drift)
    shift = (
        f"top shift {top.time:%Y-%m-%d} {top.size_pct:+.0f} % ({top.size_ft:+.2f} ft)"
        if top
        else "no shift since the reference window"
    )
    name = report.site_name or report.site
    cause = f" · likely {report.likely_cause}" if report.likely_cause else ""
    n_bad = report.drift.n_invalid_domain
    bad = f" · {n_bad} at or below rating zero (not tested)" if n_bad else ""
    return (
        f"{name} ({report.site}): {report.trust.band} {report.trust.score:.0f} · {shift}"
        f"{cause}{bad}"
    )
