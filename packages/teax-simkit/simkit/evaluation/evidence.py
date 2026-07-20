"""Runtime-owned evidence envelope.

Isolation-clean: imports only stdlib and ``simkit``-internal modules, and
never imports a generated model class. See ``design.md#required-invariants``
INV1.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Literal, Mapping

from pydantic import ConfigDict, field_validator

from ..config.schema import StrictBaseModel


def _freeze(value: Any) -> Any:
    """Recursively convert to a read-only structure: ``Mapping`` ->
    ``MappingProxyType``, ``list``/``tuple`` -> ``tuple``. The result has no
    mutable container reachable, so a downstream holder cannot change nested
    status/margin/observations (INV-C, contract 41). The three encode/decode
    walkers accept ``Mapping``/``(list, tuple)`` so the frozen tree still
    encodes byte-identically (INV-G)."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(val) for key, val in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(val) for val in value)
    return value


class CorruptConstraintEvidence(RuntimeError):
    """A constraint-bearing package (its catalog declares constraints) produced
    no constraint report — a vanished channel, not a constraint-free package
    (invariant 46a / design M3). Raised loudly, and deliberately *not* an
    ``EvaluationFailed``, so the run stops instead of recording a healthy-looking
    empty case."""

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
    ``"headline"`` for the aggregate verdict — empty (``{}``) for a
    constraint-free package. ``outputs`` holds selected numeric outputs,
    unwrapped from ``RootModel[float]``. ``report`` is the generated report's
    ``model_dump(mode="json")`` tree, deep-frozen at attach (D2) — never the
    live generated model — or ``None`` when there is no constraint report. All
    three are sealed read-only so nested status/margin cannot be mutated
    (contract 41).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    responses: Mapping[str, ResponseEntry]
    outputs: Mapping[str, float]
    provenance: EvidenceProvenance
    #: The generated report's ``model_dump(mode="json")`` tree, deep-frozen at
    #: the projection seam (D2) — or ``None`` for a constraint-free package
    #: (empty evidence, 46a). Never the live generated model.
    report: Mapping[str, Any] | None

    @field_validator("responses", "outputs", "report", mode="after")
    @classmethod
    def _seal(cls, value: Any) -> Any:
        """Deep-freeze the mappings and the report tree so no nested container
        reachable from the envelope is mutable (INV-C, contract 41)."""
        return _freeze(value)
