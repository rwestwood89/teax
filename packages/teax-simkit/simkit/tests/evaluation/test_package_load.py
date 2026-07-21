"""W5b: the loader is wired to the canonical seal protocol (Item 9's
``contracts.verify.verify_package``, imported from the package's own
``contracts/verify.py`` copy — INV-8/B3, design.md `packages/teax-simkit
design`), not the retired inlined hash check.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from simkit.evaluation.package_load import ProvisionalPackageLoader, SealVerificationError

from .conftest import FIXTURE_DIR


def _copy_package(dest: Path) -> Path:
    package_dir = dest / "package_live"
    shutil.copytree(FIXTURE_DIR, package_dir)
    return package_dir


def test_sealed_package_loads_with_verification_on(tmp_path):
    package_dir = _copy_package(tmp_path)
    loader = ProvisionalPackageLoader(
        package_dir=package_dir, package_name="wi014_s4", link_root=tmp_path / "link"
    )

    module, fingerprint = loader.load()

    assert module.__name__ == "wi014_s4"
    assert fingerprint


def test_tampered_artifact_fails_with_named_diagnostic(tmp_path):
    package_dir = _copy_package(tmp_path)
    (package_dir / "primitives.py").write_text("MUTATED\n")
    loader = ProvisionalPackageLoader(
        package_dir=package_dir, package_name="wi014_s4", link_root=tmp_path / "link"
    )

    with pytest.raises(SealVerificationError, match="TAMPER"):
        loader.load()


def test_unhashed_extra_file_fails_with_named_diagnostic(tmp_path):
    package_dir = _copy_package(tmp_path)
    (package_dir / "extra_file.py").write_text("# not part of the seal\n")
    loader = ProvisionalPackageLoader(
        package_dir=package_dir, package_name="wi014_s4", link_root=tmp_path / "link"
    )

    with pytest.raises(SealVerificationError, match="EXTRA"):
        loader.load()
