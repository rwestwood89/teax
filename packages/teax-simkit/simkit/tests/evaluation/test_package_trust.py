"""Package-trust bootstrap: the loader authenticates the verifier before running it, and
version skew fails closed (sysml-codegen Item 7 — Trusted Package Bootstrap and Seal Provenance).

Two RED-first coordinates:

- **Attack (a) — unconditional-success verifier.** A package whose ``contracts/verify.py`` is
  replaced with a stub that returns ``ok=True`` must be rejected *before its module body runs*.
  The loader hashes the verifier bytes against a vendored trust anchor and executes exactly
  those bytes, so a tampered verifier dies at the hash gate. RED against pre-fix
  ``package_load.py``, which exec'd and trusted the package-local verifier.
- **Version skew, both directions.** A seal recorded against a runtime-contract version the
  loader does not accept is rejected in either skew direction, with a diagnostic that names the
  accepted-versions policy (not the deleted bare ``"1.0.0"`` literal).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from simkit.evaluation.package_load import ProvisionalPackageLoader, SealVerificationError

F1_PACKAGE_DIR = Path(__file__).parent / "fixtures" / "f1_arithmetic" / "package_live"
PACKAGE_NAME = "f1_arithmetic_constraints"

# A malicious verifier that certifies anything. Its module body writes a marker on execution,
# so a passing test also proves no package code ran before authentication (INV-A).
STUB_VERIFIER = '''"""Unconditional-success verifier (adversarial)."""
from pathlib import Path

Path(__file__).parent.joinpath("_pwned_marker").write_text("executed")


class _Result:
    ok = True
    diagnostics: list = []


def verify_package(package_dir, package_name, runtime_version=None, strict=False):
    return _Result()
'''


def _copy_package(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg" / "package_live"
    shutil.copytree(F1_PACKAGE_DIR, pkg)
    return pkg


def test_unconditional_success_verifier_rejected_before_exec(tmp_path):
    pkg = _copy_package(tmp_path)
    (pkg / "contracts" / "verify.py").write_text(STUB_VERIFIER)

    loader = ProvisionalPackageLoader(
        package_dir=pkg, package_name=PACKAGE_NAME, link_root=tmp_path / "links"
    )
    with pytest.raises(SealVerificationError):
        loader._verify_seal()

    assert not (pkg / "contracts" / "_pwned_marker").exists(), (
        "the tampered verifier's module body executed before authentication (INV-A violated)"
    )


# Both directions around the ACCEPTED version, which moved 1.0.0 -> 2.0.0 at
# CONSTRAINT-SEMANTICS Item 3. `1.0.0` is now the older-package direction (it was the accepted
# one before the item) and `3.0.0` the newer-runtime direction.
@pytest.mark.parametrize("skewed_version", ["1.0.0", "3.0.0"])
def test_version_skew_fails_closed_both_directions(tmp_path, skewed_version):
    pkg = _copy_package(tmp_path)
    seal_path = pkg / "contracts" / "package_contract.json"
    seal = json.loads(seal_path.read_text())
    seal["runtime_contract_version"] = skewed_version
    seal_path.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n")

    loader = ProvisionalPackageLoader(
        package_dir=pkg, package_name=PACKAGE_NAME, link_root=tmp_path / "links"
    )
    with pytest.raises(SealVerificationError, match="accepted runtime-contract versions"):
        loader._verify_seal()


def test_canonical_fixture_still_loads(tmp_path):
    """Control: the untampered, re-sealed fixture authenticates and loads under the new gate."""
    loader = ProvisionalPackageLoader(
        package_dir=F1_PACKAGE_DIR, package_name=PACKAGE_NAME, link_root=tmp_path / "links"
    )
    _package, fingerprint = loader.load()
    assert len(fingerprint) == 64
