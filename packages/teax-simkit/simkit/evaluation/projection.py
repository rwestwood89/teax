"""Read-only projection from a run result + generated report into evidence.

Isolation-clean and duck-typed: never imports the generated report type,
reads it only by attribute access (``report.headline``, ``report.results``,
``r.constraint_id``, ``r.status``). See ``design.md#required-invariants``
INV1 and B1.
"""
from __future__ import annotations

from typing import Any

from .evidence import (
    CANONICAL_HEADLINE,
    CorruptConstraintEvidence,
    EvidenceProvenance,
    ModelEvidence,
)

#: The pipeline channel/field carrying the aggregated constraint report. The
#: single tolerant read of this channel lives here (D1) — both evaluator routes
#: funnel through ``project``; neither reads the channel itself.
REPORT_CHANNEL = "constraint_report"


def _is_scalar_output(value: Any) -> bool:
    """True for a duck-typed ``RootModel[float]``: has ``.root``, no report shape."""
    return hasattr(value, "root") and isinstance(value.root, (int, float))


def project(result: Any, *, provenance: EvidenceProvenance, expects_report: bool) -> ModelEvidence:
    """Project a run result into ``ModelEvidence`` — the single report-read seam.

    ``result`` need only expose ``.outputs`` (a mapping of channel/field name to
    value). The constraint report is read tolerantly here (46a):

    - present -> today's projection (headline + per-constraint responses), then
      the report is sealed into an immutable ``model_dump(mode="json")`` tree (D2);
    - absent and ``expects_report`` false -> empty constraint evidence
      (``responses={}``, ``report=None``); a constraint-free package;
    - absent and ``expects_report`` true -> ``CorruptConstraintEvidence`` (M3): a
      constraint-bearing package whose report channel vanished. Loud, never a
      silent empty case.

    ``expects_report`` is the catalog authority: the study layer derives it from
    ``load_model_contract(...).concrete_entries`` (empty iff constraint-free) and
    passes it down; the evaluator's spec-derived default agrees.
    """
    report = result.outputs.get(REPORT_CHANNEL)
    if report is None:
        if expects_report:
            raise CorruptConstraintEvidence(
                f"constraint report channel {REPORT_CHANNEL!r} is absent, but the package "
                "catalog declares constraints — the report was dropped (corruption), not "
                "a constraint-free package"
            )
        responses: dict[str, Any] = {}
        report_tree = None
    else:
        responses = {"headline": CANONICAL_HEADLINE[report.headline]}
        for constraint_result in report.results:
            responses[constraint_result.constraint_id] = constraint_result.status
        # Seal at attach: dump once here, freeze in ``ModelEvidence`` (D2). The
        # live generated model is not retained.
        report_tree = report.model_dump(mode="json")

    outputs = {
        key: float(value.root)
        for key, value in result.outputs.items()
        if _is_scalar_output(value)
    }

    return ModelEvidence(
        responses=responses,
        outputs=outputs,
        provenance=provenance,
        report=report_tree,
    )
