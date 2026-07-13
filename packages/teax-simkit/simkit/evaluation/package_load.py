"""Sealed-package loading (touches the generated package — D2).

Provisional: a symlink-under-declared-name loader with inlined seal
verification, pending Item 9's canonical package-load protocol (D7).
"""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Protocol


class SealVerificationError(Exception):
    """The on-disk package no longer matches its sealed contract."""


class PackageLoader(Protocol):
    def load(self) -> tuple[ModuleType, str]:
        """Load the sealed package, returning (module, executable_fingerprint)."""
        ...


@dataclass(frozen=True)
class ProvisionalPackageLoader:
    """Loads a sealed package tree under its declared import name.

    The package's internal imports are absolute to its declared name (e.g.
    ``from wi014_s4. ...``), so the on-disk directory is exposed under that
    name via a symlink placed in ``link_root`` (caller-supplied — this loader
    has no opinion on where that lives).
    """

    package_dir: Path
    package_name: str
    link_root: Path

    def load(self) -> tuple[ModuleType, str]:
        fingerprint = self._verify_seal()
        module = self._load_module()
        return module, fingerprint

    def _verify_seal(self) -> str:
        seal_path = self.package_dir / "contracts" / "package_contract.json"
        seal = json.loads(seal_path.read_text())
        for rel, expected in seal["artifact_hashes"].items():
            actual = hashlib.sha256((self.package_dir / rel).read_bytes()).hexdigest()
            if actual != expected:
                raise SealVerificationError(f"seal violation: {rel} hash mismatch")
        extras = {
            str(p.relative_to(self.package_dir))
            for p in self.package_dir.rglob("*")
            if p.is_file() and p != seal_path and "__pycache__" not in p.parts
        } - set(seal["artifact_hashes"])
        if extras:
            raise SealVerificationError(f"seal violation: unhashed files present: {sorted(extras)}")
        return seal["executable_fingerprint"]

    def _load_module(self) -> ModuleType:
        self.link_root.mkdir(parents=True, exist_ok=True)
        link = self.link_root / self.package_name
        if not link.exists():
            link.symlink_to(self.package_dir, target_is_directory=True)
        if str(self.link_root) not in sys.path:
            sys.path.insert(0, str(self.link_root))
        return importlib.import_module(self.package_name)
