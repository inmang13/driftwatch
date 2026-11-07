"""Pydantic v2 schemas shared by every DriftWatch module, the agents, and the API.

Conventions:
- All datetimes are timezone-aware UTC.
- Rating relationship: Q = a * (H - e) ** b. b and e are fixed from the base fit; drift slides a.
- Residual sign: r = (Q_meas - Q_hat) / Q_hat. Scour -> positive, fill -> negative.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Rated = Literal["Excellent", "Good", "Fair", "Poor", "Unspecified"]
Band = Literal["Trusted", "Watch", "Stale"]
Direction = Literal["positive", "negative"]
NodeName = Literal[
    "run", "triage", "evidence_collector", "hypothesis_ranker", "skeptic", "narrator"
]
EventStatus = Literal["started", "progress", "completed", "error"]

TRUSTED_MIN = 80
WATCH_MIN = 50


def _require_tz(v: datetime | None) -> datetime | None:
    if v is not None and v.tzinfo is None:
        raise ValueError("datetime must be timezone-aware (UTC)")
    return v


class Measurement(BaseModel):
    """One paired stage/discharge gauging (pairing itself is built later)."""

    site: str
    field_visit_id: str
    time: datetime
    stage_ft: float
    discharge_cfs: float
    rated: Rated = "Unspecified"
    control_condition: str | None = None
    approval_status: str | None = None
    excluded: bool = False  # True = kept for plots, left out of the drift test
    exclude_reason: str | None = None

    _tz = field_validator("time")(_require_tz)


class Dataset(BaseModel):
    site: str
    site_name: str | None = None
    source: Literal["snapshot", "live"]
    fetched_at: datetime | None = None
    reference_start: date
    reference_end: date
    measurements: list[Measurement] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    _tz = field_validator("fetched_at")(_require_tz)


class Relationship(BaseModel):
    """Base rating fitted on the reference window."""

    kind: Literal["power_law"] = "power_law"
    a: float
    b: float
    e: float  # gage height of zero flow, ft
    reference_start: date
    reference_end: date
    n: int = Field(ge=0)
    rmse_log: float | None = None

    def discharge(self, stage_ft: float) -> float:
        return self.a * (stage_ft - self.e) ** self.b


class StablePeriod(BaseModel):
    start: datetime
    end: datetime
    n: int = Field(ge=0)
    median_residual_pct: float | None = None

    _tz = field_validator("start", "end")(_require_tz)


class Shift(BaseModel):
    time: datetime
    size_pct: float  # % flow error vs base rating
    size_ft: float  # equivalent stage shift, ft
    direction: Direction
    n_after: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)

    _tz = field_validator("time")(_require_tz)

    @model_validator(mode="after")
    def _direction_matches_sign(self) -> Shift:
        if (self.size_pct > 0) != (self.direction == "positive") and self.size_pct != 0:
            raise ValueError(f"direction {self.direction} contradicts size_pct {self.size_pct}")
        return self


class DriftResult(BaseModel):
    site: str
    stable_periods: list[StablePeriod] = Field(default_factory=list)
    shifts: list[Shift] = Field(default_factory=list)
    n_tested: int = Field(ge=0, default=0)
    n_excluded: int = Field(ge=0, default=0)
    penalty: float | None = None


class Deduction(BaseModel):
    name: str
    points: float = Field(ge=0)
    reason: str


class TrustScore(BaseModel):
    """Glass-box score: 100 minus the listed deductions, floored at 0."""

    score: float = Field(ge=0, le=100)
    band: Band
    deductions: list[Deduction] = Field(default_factory=list)

    @staticmethod
    def band_for(score: float) -> Band:
        if score >= TRUSTED_MIN:
            return "Trusted"
        if score >= WATCH_MIN:
            return "Watch"
        return "Stale"

    @classmethod
    def from_deductions(cls, deductions: list[Deduction]) -> TrustScore:
        score = max(0.0, 100.0 - sum(d.points for d in deductions))
        return cls(score=score, band=cls.band_for(score), deductions=deductions)

    @model_validator(mode="after")
    def _arithmetic_matches(self) -> TrustScore:
        expected = max(0.0, 100.0 - sum(d.points for d in self.deductions))
        if abs(self.score - expected) > 1e-6:
            raise ValueError(f"score {self.score} != 100 - deductions ({expected})")
        if self.band != self.band_for(self.score):
            raise ValueError(f"band {self.band} does not match score {self.score}")
        return self


class Report(BaseModel):
    site: str
    site_name: str | None = None
    generated_at: datetime
    source: Literal["snapshot", "live"]
    relationship: Relationship
    drift: DriftResult
    trust: TrustScore
    likely_cause: str | None = None
    narrative: str | None = None

    _tz = field_validator("generated_at")(_require_tz)


class TraceEvent(BaseModel):
    run_id: str
    site: str
    seq: int = Field(ge=0)
    ts: datetime
    node: NodeName
    status: EventStatus
    payload: dict[str, Any] = Field(default_factory=dict)

    _tz = field_validator("ts")(_require_tz)
