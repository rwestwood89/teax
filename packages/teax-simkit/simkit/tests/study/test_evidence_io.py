"""Evidence serialization: lossless non-finite round-trip (INV-H, D3) and the
reserved-key rejection (MF-3).
"""
from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import BaseModel

from simkit.evaluation.evidence import EvidenceProvenance, ModelEvidence
from simkit.study.evidence_io import encode_evidence
from simkit.study.identity import canonical_bytes

from .conftest import ENTRY_CH, FIXED


def test_evidence_roundtrip_nonfinite(prepared):  # INV-H, D3
    params = prepared.ToyPlantParams(toy_plant__Toy_Plant__plant_budget=float("nan"), **FIXED)
    evidence = prepared.evaluate({ENTRY_CH: params})

    encoded = encode_evidence(evidence)
    payload = canonical_bytes(encoded)
    digest = hashlib.sha256(payload).hexdigest()

    # Standard, re-parseable JSON: no bare NaN/Infinity token survives.
    reloaded = json.loads(payload)
    assert reloaded == encoded
    assert hashlib.sha256(canonical_bytes(reloaded)).hexdigest() == digest


class _PoisonedReport(BaseModel):
    model_config = {"extra": "allow"}

    weird: dict


def test_reserved_key_rejected():  # MF-3
    provenance = EvidenceProvenance(
        executable_fingerprint="f", evidence_schema_version="v1",
        evaluator_version="v1", input_digest="d",
    )
    evidence = ModelEvidence(
        responses={"headline": "satisfied"}, outputs={}, provenance=provenance,
        report=_PoisonedReport(weird={"__nonfinite__": "nan"}),
    )
    with pytest.raises(ValueError, match="__nonfinite__"):
        encode_evidence(evidence)
