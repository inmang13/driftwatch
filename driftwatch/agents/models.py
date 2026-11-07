"""Structured outputs for the LLM nodes (and their deterministic fallbacks, which return the same
types). Cause keys come from the catalog in modules/rating_curve/causes.py plus 'inconclusive'."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from driftwatch.modules.rating_curve.causes import CAUSES

CAUSE_KEYS: tuple[str, ...] = tuple(c.key for c in CAUSES) + ("inconclusive",)
CauseKey = Literal[
    "scour",
    "fill",
    "debris",
    "vegetation",
    "datum_change",
    "measurement_quality",
    "insufficient_data",
    "inconclusive",
]
REQUIRED_CAUSES = ("datum_change", "inconclusive")


class Hypothesis(BaseModel):
    cause: CauseKey
    confidence: float = Field(ge=0.0, le=1.0, description="0..1; all listed sum to about 1")
    sign_matches: bool = Field(description="cause's expected residual sign fits the observed one")
    evidence: list[str] = Field(default_factory=list, description="short facts for and against")


class Ranking(BaseModel):
    """Ranked causes, most likely first. Always lists datum_change and inconclusive."""

    hypotheses: list[Hypothesis]
    reasoning: str = Field(default="", description="two sentences at most")

    @property
    def top(self) -> Hypothesis:
        return self.hypotheses[0]


class SkepticVerdict(BaseModel):
    verdict: Literal["accept", "object"]
    objection: (
        Literal["sign_mismatch", "channel_evidence", "insufficient_evidence", "other"] | None
    ) = None
    argument: str = Field(description="one or two sentences citing the numbers")
    suggested_cause: CauseKey | None = None


class Narration(BaseModel):
    text: str = Field(description="<= 120 words for a utility manager")
