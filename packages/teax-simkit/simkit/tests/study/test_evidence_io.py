"""Evidence serialization: lossless non-finite round-trip (INV-H, D3) and the
reserved-key rejection (MF-3).
"""
from __future__ import annotations

import hashlib
import json
import math

import pytest

from simkit.evaluation.evidence import EvidenceProvenance, ModelEvidence
from simkit.study.evidence_io import decode_evidence, encode_evidence
from simkit.study.identity import canonical_bytes

from .conftest import ENTRY_CH, FIXED


def test_evidence_roundtrip_nonfinite(prepared):  # INV-H, D3
    params = prepared.entry_models[ENTRY_CH](toy_plant__Toy_Plant__plant_budget=float("nan"), **FIXED)
    evidence = prepared.evaluate({ENTRY_CH: params})

    encoded = encode_evidence(evidence)
    payload = canonical_bytes(encoded)
    digest = hashlib.sha256(payload).hexdigest()

    # Standard, re-parseable JSON: no bare NaN/Infinity token survives.
    reloaded = json.loads(payload)
    assert reloaded == encoded
    assert hashlib.sha256(canonical_bytes(reloaded)).hexdigest() == digest


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_decode_is_exact_inverse_of_encode(value):  # INV-3
    provenance = EvidenceProvenance(
        executable_fingerprint="f", evidence_schema_version="v1",
        evaluator_version="v1", input_digest="d",
    )
    evidence = ModelEvidence(
        responses={"headline": "indeterminate", "c1": "indeterminate"},
        outputs={"x": value},
        provenance=provenance,
        report={"observed": {"y": value}},  # sealed model_dump tree (D2): real non-finite floats
    )

    decoded = decode_evidence(encode_evidence(evidence))

    def is_same_nonfinite(a, b):
        if math.isnan(a):
            return math.isnan(b)
        return a == b

    assert is_same_nonfinite(decoded["outputs"]["x"], value)
    assert is_same_nonfinite(decoded["report"]["observed"]["y"], value)
    assert "__nonfinite__" not in json.dumps(decoded)


def test_reserved_key_rejected():  # MF-3
    provenance = EvidenceProvenance(
        executable_fingerprint="f", evidence_schema_version="v1",
        evaluator_version="v1", input_digest="d",
    )
    evidence = ModelEvidence(
        responses={"headline": "satisfied"}, outputs={}, provenance=provenance,
        report={"weird": {"__nonfinite__": "nan"}},  # poison inside the sealed report tree (MF-3)
    )
    with pytest.raises(ValueError, match="__nonfinite__"):
        encode_evidence(evidence)
