"""Item 8: `load_model_contract` fails closed on catalog-schema skew, both directions (INV-4).

The seam reads codegen's embedded catalog from `contracts/model_contract.json` and rejects any
`catalog_schema_version` outside the vendored accepted set *before* reading a catalog field —
whether the package is newer or older than the runtime, or carries no version at all.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from simkit.evaluation.package_load import ACCEPTED_CATALOG_SCHEMA_VERSIONS
from simkit.study.model_contract import IncompatibleCatalogSchema, load_model_contract

ACCEPTED = sorted(ACCEPTED_CATALOG_SCHEMA_VERSIONS)[0]


def _write_contract(package_dir: Path, version) -> None:
    contracts = package_dir / "contracts"
    contracts.mkdir(parents=True)
    payload = {
        "semantic_fingerprint": "sem-fp-xyz",
        "constraint_catalog": {
            "concrete_entries": [
                {
                    "constraint_id": "C1",
                    "source_form": "inline",
                    "owner_qualified_name": "Pkg::Part",
                    "definition_qualified_name": None,
                    "membership_kind": "assert",
                    "is_negated": False,
                    "predicate_ir": '{"kind":"literal"}',
                }
            ],
            "usage_records": [],
        },
    }
    if version is not _MISSING:
        payload["catalog_schema_version"] = version
    (contracts / "model_contract.json").write_text(json.dumps(payload))


_MISSING = object()


def test_accepted_version_loads(tmp_path):
    _write_contract(tmp_path, ACCEPTED)
    data = load_model_contract(tmp_path)
    assert data.semantic_fingerprint == "sem-fp-xyz"
    assert data.catalog_schema_version == ACCEPTED
    assert set(data.concrete_entries) == {"C1"}


def test_newer_version_fails_closed(tmp_path):
    _write_contract(tmp_path, "999.0.0")
    with pytest.raises(IncompatibleCatalogSchema, match="not accepted"):
        load_model_contract(tmp_path)


def test_older_version_fails_closed(tmp_path):
    _write_contract(tmp_path, "1.0.0")
    with pytest.raises(IncompatibleCatalogSchema, match="not accepted"):
        load_model_contract(tmp_path)


def test_missing_version_fails_closed(tmp_path):
    """An ancient package with no catalog_schema_version token is rejected, not defaulted."""
    _write_contract(tmp_path, _MISSING)
    with pytest.raises(IncompatibleCatalogSchema):
        load_model_contract(tmp_path)


def test_real_fingerprint_is_read_not_a_byte_hash(tmp_path):
    """The bound identity is codegen's semantic_fingerprint, verbatim — not a hash of bytes."""
    _write_contract(tmp_path, ACCEPTED)
    assert load_model_contract(tmp_path).semantic_fingerprint == "sem-fp-xyz"
