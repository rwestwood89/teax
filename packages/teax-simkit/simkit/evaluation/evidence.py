"""Runtime-owned evidence envelope.

Isolation-clean: imports only stdlib and ``simkit``-internal modules, and
never imports a generated model class. See ``design.md#required-invariants``
INV1.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Literal, Mapping

from ..config.schema import StrictBaseModel

# Runtime-owned verdict vocabulary. A per-constraint status is one of the
# first three; the aggregate headline can additionally be "not_assessed".
ResponseEntry = Literal["satisfied", "violated", "indeterminate", "not_assessed"]

# Read-only projection from the generated report's headline vocabulary
# (underscore) onto the runtime-owned canonical vocabulary (D6).
CANONICAL_HEADLINE: Mapping[str, ResponseEntry] = MappingProxyType(
    {
        "all_satisfied": "satisfied",
        "violation": "violated",
        "indeterminate": "indeterminate",
        "not_assessed": "not_assessed",
    }
)


class EvidenceProvenance(StrictBaseModel):
    """Identity fields the evaluator is entitled to stamp.

    Deliberately excludes study/candidate/proposal identity and wall-clock
    timestamps — those are runner-owned (Item 11) and stamping them here
    would break determinism (B2). See
    ``design.md#deferred-item-decisions``.
    """

    executable_fingerprint: str
    evidence_schema_version: str
    evaluator_version: str
    input_digest: str


class ModelEvidence(StrictBaseModel):
    """Immutable evidence produced by one evaluation.

    ``responses`` is keyed by constraint ID plus the reserved key
    ``"headline"`` for the aggregate verdict. ``outputs`` holds selected
    numeric outputs, unwrapped from ``RootModel[float]``. ``report`` is the
    generated report object, held opaque (``Any``) and never introspected by
    this module.
    """

    responses: Mapping[str, ResponseEntry]
    outputs: Mapping[str, float]
    provenance: EvidenceProvenance
    report: Any
