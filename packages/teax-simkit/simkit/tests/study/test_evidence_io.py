"""Evidence serialization: lossless non-finite round-trip (INV-H, D3) and the
reserved-key rejection (MF-3).
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Dict

import pytest
from pydantic import BaseModel

from simkit.evaluation.evidence import EvidenceProvenance, ModelEvidence
from simkit.study.evidence_io import decode_evidence, encode_evidence
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


class _TypedReport(BaseModel):
    """A typed float(-mapping) field, mirroring a generated report's
    `observed: dict[str, float]` (constraint_types.py) — the shape that
    actually preserves non-finite values through `model_dump(mode="json")`;
    an untyped `dict` field coerces inf/nan to `null` before `_tag_nonfinite`
    ever sees them."""

    observed: Dict[str, float]


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
        report=_TypedReport(observed={"y": value}),
    )

    decoded = decode_evidence(encode_evidence(evidence))

    def is_same_nonfinite(a, b):
        if math.isnan(a):
            return math.isnan(b)
        return a == b

    assert is_same_nonfinite(decoded["outputs"]["x"], value)
    assert is_same_nonfinite(decoded["report"]["observed"]["y"], value)
    assert "__nonfinite__" not in json.dumps(decoded)


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
