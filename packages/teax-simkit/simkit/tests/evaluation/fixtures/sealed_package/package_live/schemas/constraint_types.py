"""Constraint evidence schemas (S4 test-only shapes)."""

from typing import Literal, Optional

from pydantic import BaseModel


class ConstraintEvaluation(BaseModel):
    """One assertion verdict in one concrete context. Violation is evidence,
    never an exception."""

    constraint_id: str
    actual_value: Optional[bool] = None
    status: Literal["satisfied", "violated", "indeterminate"]
    margin: Optional[float] = None
    observed: dict[str, float]


class ConstraintReport(BaseModel):
    """Assertion evidence and coverage for one design point."""

    catalog_fingerprint: str
    assessed_count: int
    headline: Literal["violation", "indeterminate", "all_satisfied", "not_assessed"]
    results: list[ConstraintEvaluation]
