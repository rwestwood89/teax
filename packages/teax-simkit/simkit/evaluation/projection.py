"""Read-only projection from a run result + generated report into evidence.

Isolation-clean and duck-typed: never imports the generated report type,
reads it only by attribute access (``report.headline``, ``report.results``,
``r.constraint_id``, ``r.status``). See ``design.md#required-invariants``
INV1 and B1.
"""
from __future__ import annotations

from typing import Any

from .evidence import CANONICAL_HEADLINE, EvidenceProvenance, ModelEvidence


def _is_scalar_output(value: Any) -> bool:
    """True for a duck-typed ``RootModel[float]``: has ``.root``, no report shape."""
    return hasattr(value, "root") and isinstance(value.root, (int, float))


def project(result: Any, report: Any, *, provenance: EvidenceProvenance) -> ModelEvidence:
    """Project a run result and its opaque report into ``ModelEvidence``.

    ``result`` need only expose ``.outputs`` (a mapping of channel/field name
    to value); ``report`` need only expose ``.headline`` and ``.results``
    (each with ``.constraint_id`` and ``.status``). The report is attached
    unchanged — never mutated, never introspected beyond these reads.
    """
    responses = {"headline": CANONICAL_HEADLINE[report.headline]}
    for constraint_result in report.results:
        responses[constraint_result.constraint_id] = constraint_result.status

    outputs = {
        key: float(value.root)
        for key, value in result.outputs.items()
        if _is_scalar_output(value)
    }

    return ModelEvidence(
        responses=responses,
        outputs=outputs,
        provenance=provenance,
        report=report,
    )
