"""Deterministic stand-ins for the three LLM nodes (LLM=fallback). Same output types as the LLM.

Ranker: score every catalog cause on the evidence the ranker is given (residual sign, field
notes, the M1 call, the shape of the shift, measurement quality). Channel geometry is *not* used
here on purpose: it is the skeptic's cross-check, so the two nodes look at different evidence.
Causes whose expected sign contradicts the residual get confidence 0. datum_change and
inconclusive are always listed. A skeptic objection demotes the objected cause and promotes the
one the skeptic suggested.

Skeptic: object when the top cause's expected sign contradicts the residual, or when the channel
geometry contradicts it (speed fell much more than area changed -> something is holding the
water back, i.e. fill/backwater on the downstream control, not a datum change or scour).

Narrator: a template.
"""

from __future__ import annotations

from typing import Any

from driftwatch.agents.models import (
    REQUIRED_CAUSES,
    BestGuess,
    Disagreement,
    FieldNoteRef,
    Hypothesis,
    Narration,
    Ranking,
    SkepticVerdict,
)
from driftwatch.core import trust
from driftwatch.modules.rating_curve import causes as catalog

# Channel signature thresholds (decision log 2026-11-07, M2). Percent change at the same stage.
SPEED_MIN_PCT = 15.0  # velocity must move at least this much to count
SPEED_VS_AREA = 1.5  # ... and by at least this multiple of the area change
AREA_ONLY_PCT = 15.0  # area moved this much while speed moved < half as much

DATA_TARGET_PER_YEAR = trust.DATA_TARGET_PER_YEAR  # same target as the trust score
INSUFFICIENT_DATA_POINTS = 2
PERSISTENT_MIN_AFTER = 4  # a shift with this many measurements since it is a persistent step
OBJECTION_PENALTY = 3
SUGGESTION_BONUS = 2

LABEL = {c.key: c.label for c in catalog.CAUSES} | {"inconclusive": "Inconclusive"}

NEXT_STEP = {
    "scour": "Schedule a field measurement and a control survey, then apply a positive shift "
    "until a new rating is built.",
    "fill": "Schedule a field visit to survey the control and apply a negative shift; plan a "
    "rating revision if the next two measurements agree.",
    "debris": "Ask the field crew to clear the control on the next visit and re-measure; "
    "treat published flows as high until then.",
    "vegetation": "Check the control for growth on the next visit; expect it to fade after "
    "the growing season.",
    "datum_change": "Pull the gauge's levels and maintenance history and re-run levels to the "
    "reference marks before changing the rating.",
    "measurement_quality": "Get one Good-rated measurement at moderate flow before acting on "
    "the drift.",
    "insufficient_data": "Add field measurements; there are too few recent ones to tell drift "
    "from noise.",
    "inconclusive": "Get another field measurement and a control inspection before changing "
    "the rating.",
}


def channel_signature(ch: dict | None) -> str:
    """'backwater' (speed fell much more than area changed), 'faster' (speed rose much more),
    'area_only' (area moved, speed didn't), 'mixed', or 'unknown' (not enough data)."""
    if not ch or not ch.get("sufficient"):
        return "unknown"
    da, dv = ch["area_change_pct"], ch["velocity_change_pct"]
    if dv <= -SPEED_MIN_PCT and abs(dv) >= SPEED_VS_AREA * abs(da):
        return "backwater"
    if dv >= SPEED_MIN_PCT and abs(dv) >= SPEED_VS_AREA * abs(da):
        return "faster"
    if abs(da) >= AREA_ONLY_PCT and abs(dv) < 0.5 * abs(da):
        return "area_only"
    return "mixed"


def _sign_ok(key: str, direction: str) -> bool:
    if key in ("inconclusive", "insufficient_data"):  # no expected sign; never ruled out by it
        return True
    return catalog.sign_agrees(catalog.get_cause(key), direction)


def rank(facts: dict[str, Any], objections: list[dict] | None = None) -> Ranking:
    t = facts["triage"]
    direction = t["direction"]
    notes = facts["field_notes"]["visits"]
    latest = (facts["field_notes"].get("latest_note") or "").lower()
    shift = t.get("top_shift")
    persistent = bool(shift and shift["n_after"] >= PERSISTENT_MIN_AFTER)
    score: dict[str, int] = {}
    why: dict[str, list[str]] = {}

    def add(key: str, pts: int, reason: str) -> None:
        score[key] = score.get(key, 0) + pts
        why.setdefault(key, []).append(reason)

    for key in ("scour", "fill", "debris", "vegetation", "datum_change", "measurement_quality"):
        score[key] = 0
        why[key] = []
    score["inconclusive"] = 1
    why["inconclusive"] = ["baseline: no cause is ever certain from gaugings alone"]

    seen: set[str] = set()
    for v in notes:
        c = catalog.cause_for_note(v["note"])
        if not c or v["note"] in seen:
            continue
        seen.add(v["note"])
        control = "control changed" in v["note"].lower()
        if catalog.sign_agrees(c, direction):
            add(c.key, 2 if control else 1, f"field note '{v['note']}' ({v['time'][:10]})")
        elif control:
            add(
                "datum_change",
                1,
                f"note '{v['note']}' contradicts the {direction} residual (a rebuild or datum "
                "change fits the sign)",
            )
            why[c.key].append(f"note '{v['note']}' but its sign contradicts the residual")
    for key in ("debris", "vegetation"):
        if latest.startswith(key):
            add(key, 1, f"latest visit still notes '{facts['field_notes']['latest_note']}'")
    if persistent:
        for key in ("scour", "fill"):
            if _sign_ok(key, direction):
                add(
                    key,
                    1,
                    f"persistent step: {shift['n_after']} measurements since {shift['time'][:10]}",
                )
        if shift["confidence"] >= 0.95:
            add(
                "datum_change",
                1,
                f"sharp step at one visit ({shift['time'][:10]}, " f"{shift['size_pct']:+.0f} %)",
            )
    else:
        add("inconclusive", 1, "no persistent post-storm step detected")
    rated = t.get("recent_rated") or []
    rough = sum(1 for r in rated if r in ("Poor", "Fair"))
    if rated and rough * 2 > len(rated):
        add(
            "measurement_quality", 1, f"{rough} of {len(rated)} recent measurements rated Poor/Fair"
        )
    n_year = t.get("n_visits_last_12_months")
    if n_year is not None and n_year < DATA_TARGET_PER_YEAR:
        score["insufficient_data"] = score.get("insufficient_data", 0)
        why.setdefault("insufficient_data", [])
        add(
            "insufficient_data",
            INSUFFICIENT_DATA_POINTS,
            f"only {n_year} field measurements in the last 12 months (target "
            f"{DATA_TARGET_PER_YEAR})",
        )
    if t.get("m1_cause") in score:
        add(t["m1_cause"], 1, "the M1 rule-based triage named it")

    for o in objections or []:
        bad = o.get("objected_cause")
        if bad in score:
            add(bad, -OBJECTION_PENALTY, f"skeptic objected: {o.get('argument', '')[:120]}")
        good = o.get("suggested_cause")
        if good in score:
            add(good, SUGGESTION_BONUS, "skeptic's suggested alternative")

    for key in list(score):
        if not _sign_ok(key, direction):
            score[key] = 0
        score[key] = max(score[key], 0)
    keep = [k for k in score if _sign_ok(k, direction) and (score[k] > 0 or k in REQUIRED_CAUSES)]
    keep += [k for k in score if not _sign_ok(k, direction) and why[k]]  # ruled out, say why
    total = sum(score[k] for k in keep) or 1
    hyps = [
        Hypothesis(
            cause=k,
            confidence=round(score[k] / total, 2),
            sign_matches=_sign_ok(k, direction),
            evidence=why[k] or ["no specific evidence"],
        )
        for k in keep
    ]
    # most evidence first; ties: persistent causes before 'either' ones, catalog order after
    order = {k: i for i, k in enumerate(score)}
    hyps.sort(key=lambda h: (-h.confidence, h.cause == "inconclusive", order[h.cause]))
    top = hyps[0]
    return Ranking(
        hypotheses=hyps,
        reasoning=f"{LABEL[top.cause]} has the most evidence that fits a {direction} residual.",
    )


def critique(facts: dict[str, Any], ranking: Ranking) -> SkepticVerdict:
    t = facts["triage"]
    direction = t["direction"]
    top = ranking.top
    ch = facts.get("channel_geometry") or {}
    sig = channel_signature(ch)
    nums = (
        f"area {ch['area_change_pct']:+.0f} %, speed {ch['velocity_change_pct']:+.0f} % at "
        f"{ch['at_stage_ft']} ft"
        if ch.get("sufficient")
        else "no usable channel comparison"
    )
    if not _sign_ok(top.cause, direction):
        alt = next((h.cause for h in ranking.hypotheses[1:] if h.sign_matches), "inconclusive")
        return SkepticVerdict(
            verdict="object",
            objection="sign_mismatch",
            argument=f"{LABEL[top.cause]} would push the residual the other way; the gauge reads "
            f"{t['recent_median_residual_pct']:+.0f} %.",
            suggested_cause=alt,
        )
    if sig == "backwater" and top.cause in ("datum_change", "scour"):
        alt = "fill" if direction == "negative" else "inconclusive"
        return SkepticVerdict(
            verdict="object",
            objection="channel_evidence",
            argument=f"At the same stage the water moves much slower while the section barely "
            f"changed ({nums}). Something downstream is holding the water back: fill or "
            f"backwater on the control, not a {LABEL[top.cause].lower()}.",
            suggested_cause=alt,
        )
    if sig == "faster" and top.cause in ("fill", "debris", "vegetation", "datum_change"):
        alt = "scour" if direction == "positive" else "inconclusive"
        return SkepticVerdict(
            verdict="object",
            objection="channel_evidence",
            argument=f"At the same stage the water moves much faster ({nums}), which is a "
            f"lowered control, not {LABEL[top.cause].lower()}.",
            suggested_cause=alt,
        )
    return SkepticVerdict(
        verdict="accept",
        objection=None,
        argument=f"{LABEL[top.cause]} fits the {direction} residual and the channel check "
        f"({nums}; pattern: {sig}).",
        suggested_cause=None,
    )


DISAGREE_BELOW = 0.6  # skeptic confidence under this + a contradicting control note -> Disagreement
NOTE_DISCOUNT = (
    0.2  # the rules' skeptic trusts a cause this much less when a control note disagrees
)

# what to check on the next visit, by (what the note says, what the numbers say)
RECOMMENDED_CHECK = {
    ("scour", "fill"): "Survey the control section for deposited gravel and confirm the gauge "
    "datum against the reference mark.",
    ("scour", "datum_change"): "Run levels from the reference marks to the gauge to confirm the "
    "datum, and survey the control for scour.",
    ("fill", "scour"): "Survey the control for scour and confirm the gauge datum against the "
    "reference mark.",
}
DEFAULT_CHECK = "Survey the control section and confirm the gauge datum against the reference mark."


def contradicting_note(facts: dict[str, Any], cause: str) -> dict[str, str] | None:
    """First 'control changed' note since the reference window whose cause is not `cause`."""
    for v in facts.get("field_notes", {}).get("visits", []):
        c = catalog.cause_for_note(v["note"])
        if c and "control changed" in v["note"].lower() and c.key != cause:
            return {"note": v["note"], "date": v["time"][:10], "cause": c.key}
    return None


def skeptic_confidence(facts: dict[str, Any], ranking: Ranking) -> float:
    """The rules' skeptic: the ranker's confidence, discounted when a control note disagrees."""
    c = ranking.top.confidence
    if contradicting_note(facts, ranking.top.cause):
        c -= NOTE_DISCOUNT
    return round(max(c, 0.0), 2)


def disagreement(facts: dict[str, Any], ranking: Ranking, confidence: float) -> Disagreement | None:
    """Disagreement for the final verdict, or None when the rules don't call for one."""
    top = ranking.top
    note = contradicting_note(facts, top.cause)
    if note is None or confidence >= DISAGREE_BELOW:
        return None
    t = facts["triage"]
    ch = facts.get("channel_geometry") or {}
    implied = catalog.get_cause(note["cause"])
    want = {"positive": "above", "negative": "below"}.get(implied.expected_sign, "off")
    nums = (
        f"; at the same stage the flow area changed {ch['area_change_pct']:+.0f} % and the speed "
        f"{ch['velocity_change_pct']:+.0f} %"
        if ch.get("sufficient")
        else ""
    )
    why = (
        f"{implied.label} would put measurements {want} the rating, but they sit "
        f"{t['off_by_pct']:.0f} % {t['direction_phrase']}{nums}, which fits "
        f"{LABEL[top.cause].lower()} better."
    )
    return Disagreement(
        best_guess=BestGuess(cause=top.cause, confidence=confidence),
        field_note=FieldNoteRef(note=note["note"], date=note["date"]),
        why_they_disagree=why,
        recommended_check=RECOMMENDED_CHECK.get((note["cause"], top.cause), DEFAULT_CHECK),
    )


def narrate(facts: dict[str, Any], final: dict[str, Any] | None) -> Narration:
    t = facts["triage"]
    name = t.get("site_name") or t["site"]
    score = f"Trust score {t['score']:.0f}/100 ({t['band']})."
    off = f"{t['off_by_pct']:.0f} % {t['direction_phrase']}"
    if final is None:
        return Narration(
            text=f"{name}: no lasting shift since the storm; recent field measurements average "
            f"{off}, so published flows can be used as is. No action beyond the regular visit "
            f"schedule. {score}"
        )
    shift = t.get("top_shift")
    since = f" (the shift began {shift['time'][:10]})" if shift else ""
    what = (
        f"{name}: recent field measurements{since} sit {off}, so published flows are about "
        f"that much {t['published_flows']}."
    )
    d = final.get("disagreement")
    if d:
        bg = d["best_guess"]
        return Narration(
            text=f"{what} Best guess: {LABEL[bg['cause']].lower()} ({bg['confidence'] * 100:.0f} "
            f"%, uncertain). The field note says \"{d['field_note']['note']}\" "
            f"({d['field_note']['date']}). Why they disagree: {d['why_they_disagree']} "
            f"Double-check: {d['recommended_check']} {score}"
        )
    cause = final["cause"]
    conf = final["confidence"]
    sure = "confident" if conf >= 0.8 else "likely" if conf >= 0.4 else "uncertain"
    objected = (
        f" A second check overturned the first guess ({LABEL[final['first_cause']].lower()})."
        if final.get("first_cause") and final["first_cause"] != cause
        else ""
    )
    if final.get("unresolved"):
        objected += " A reviewer still disputes it, so treat the cause as unconfirmed."
    return Narration(
        text=f"{what} Most likely cause: {LABEL[cause].lower()} — {sure} "
        f"({conf * 100:.0f} %).{objected} Next: {NEXT_STEP[cause]} {score}"
    )
