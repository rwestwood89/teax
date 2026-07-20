"""`StudyQuery`: the read-only join a `teax-study inspect` renders (D6, D7).

Reads `cases` rows from the store, decodes each referenced evidence artifact
once (memoized by `evidence_digest`), and joins per-constraint verdicts to
codegen's embedded catalog by `constraint_id` (Item 8). The catalog entry now
carries source form, usage identity, owner QN, and the definition→usage join
directly — so the view is built from the entry itself, with no standalone
`constraint_catalog.json` and no reconstruction. Every result carries its
`executable_fingerprint`; results are never merged across fingerprints (INV-5).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .evidence_io import decode_evidence
from .model_contract import load_model_contract
from .store import StudyStore


@dataclass(frozen=True)
class CatalogView:
    constraint_id: str
    source_form: str
    membership_kind: str | None
    is_negated: bool
    owner_qn: str
    #: The referenced constraint def's QN — `None` for inline usages (F1).
    definition_qn: str | None
    predicate_ir: str


@dataclass(frozen=True)
class CaseView:
    candidate_id: str
    state: str
    inputs: Mapping[str, Any]
    outputs: Mapping[str, float]
    verdicts: Mapping[str, str]  # constraint_id -> satisfied|violated|indeterminate|not_assessed
    headline: str | None
    disposition: str | None
    assessment: Mapping[str, Any] | None
    executable_fingerprint: str
    evidence_digest: str | None
    catalog: Mapping[str, CatalogView]  # constraint_id -> joined static detail


class _Catalog:
    """Reads codegen's embedded catalog from the model contract and views entries by id.

    Every field the view needs is carried on the concrete entry itself (Item 8): source form,
    owner QN, the definition→usage join, and predicate IR. No standalone catalog file, no
    `source_usage -> source_record` reconstruction.
    """

    def __init__(self, package_dir: str | Path) -> None:
        self._entries = load_model_contract(package_dir).concrete_entries

    def view_for(self, constraint_id: str) -> CatalogView | None:
        entry = self._entries.get(constraint_id)
        if entry is None:
            return None
        return CatalogView(
            constraint_id=constraint_id,
            source_form=entry["source_form"],
            membership_kind=entry["membership_kind"],
            is_negated=entry["is_negated"],
            owner_qn=entry["owner_qualified_name"],
            definition_qn=entry["definition_qualified_name"],
            predicate_ir=entry["predicate_ir"],
        )


class StudyQuery:
    def __init__(self, store: StudyStore, package_dir: str | Path) -> None:
        self.store = store
        self._catalog = _Catalog(package_dir)
        self._evidence_cache: dict[str, dict[str, Any]] = {}
        self._store_fingerprint = self.store.conn.execute(
            "SELECT executable_fingerprint FROM compatibility"
        ).fetchone()[0]

    def _decoded_evidence(self, digest: str) -> dict[str, Any]:
        if digest not in self._evidence_cache:
            path = self.store.artifacts_dir / f"{digest}.json"
            raw = json.loads(path.read_text())
            self._evidence_cache[digest] = decode_evidence(raw)
        return self._evidence_cache[digest]

    def _case_view(self, row: dict[str, Any]) -> CaseView:
        outputs: Mapping[str, float] = {}
        verdicts: dict[str, str] = {}
        headline = None
        fingerprint = self._store_fingerprint
        if row["evidence_digest"] is not None:
            evidence = self._decoded_evidence(row["evidence_digest"])
            outputs = evidence["outputs"]
            responses = dict(evidence["responses"])
            headline = responses.pop("headline", None)
            verdicts = responses
            fingerprint = evidence["provenance"]["executable_fingerprint"]

        catalog = {
            constraint_id: view
            for constraint_id in verdicts
            if (view := self._catalog.view_for(constraint_id)) is not None
        }
        assessment = json.loads(row["assessment_json"]) if row["assessment_json"] else None

        return CaseView(
            candidate_id=row["candidate_id"],
            state=row["state"],
            inputs=json.loads(row["inputs_json"]),
            outputs=outputs,
            verdicts=verdicts,
            headline=headline,
            disposition=assessment.get("disposition") if assessment else None,
            assessment=assessment,
            executable_fingerprint=fingerprint,
            evidence_digest=row["evidence_digest"],
            catalog=catalog,
        )

    def cases(
        self,
        *,
        parameter: str | None = None,
        output: str | None = None,
        constraint: str | None = None,
        state: str | None = None,
        disposition: str | None = None,
    ) -> list[CaseView]:
        """All cases, or those matching every given filter. `parameter`/
        `output`/`constraint` filter on key presence in the case's
        inputs/outputs/verdicts; `state`/`disposition` filter on exact
        value.
        """
        views = [self._case_view(row) for row in self.store.ordered_cases()]
        if parameter is not None:
            views = [v for v in views if parameter in v.inputs]
        if output is not None:
            views = [v for v in views if output in v.outputs]
        if constraint is not None:
            views = [v for v in views if constraint in v.verdicts]
        if state is not None:
            views = [v for v in views if v.state == state]
        if disposition is not None:
            views = [v for v in views if v.disposition == disposition]
        return views
