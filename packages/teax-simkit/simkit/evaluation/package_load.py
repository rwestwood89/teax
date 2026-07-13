"""Sealed-package loading (touches the generated package — D2).

Seal verification is wired to the canonical protocol from sysml-codegen's Item 9
(``contracts.verify.verify_package``): every generated package carries its own copy of
that stdlib-only module at ``contracts/verify.py`` (INV-8), and this loader imports that
copy from the package tree it is loading rather than depending on sysml-codegen being
installed (B3) — a teax environment verifies a package it loaded with nothing but the
package itself. The symlink-under-declared-name import mechanism below is unrelated and
unchanged.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Protocol

RUNTIME_CONTRACT_VERSION = "1.0.0"
"""The runtime API surface this loader targets — teax's own copy of the marker a
package's seal was recorded against (``sysml_codegen.contracts.versions.RUNTIME_CONTRACT_VERSION``
at seal time). Bump alongside a breaking change to that surface."""


class SealVerificationError(Exception):
    """The on-disk package no longer matches its sealed contract."""


class PackageLoader(Protocol):
    def load(self) -> tuple[ModuleType, str]:
        """Load the sealed package, returning (module, executable_fingerprint)."""
        ...


def _load_verify_package(package_dir: Path):
    """Import the package's own ``contracts/verify.py`` (INV-8) by file path.

    Not a package-qualified import: the module lives inside the tree being verified,
    before that tree is exposed on ``sys.path`` under its declared name.
    """
    verify_path = package_dir / "contracts" / "verify.py"
    spec = importlib.util.spec_from_file_location("_package_contract_verify", verify_path)
    if spec is None or spec.loader is None:
        raise SealVerificationError(f"seal violation: cannot load verifier at {verify_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    strict: bool = True

    def load(self) -> tuple[ModuleType, str]:
        fingerprint = self._verify_seal()
        module = self._load_module()
        return module, fingerprint

    def _verify_seal(self) -> str:
        verify = _load_verify_package(self.package_dir)
        result = verify.verify_package(
            self.package_dir,
            self.package_name,
            runtime_version=RUNTIME_CONTRACT_VERSION,
            strict=self.strict,
        )
        if not result.ok:
            details = "; ".join(f"{d.kind}({d.path}): {d.message}" for d in result.diagnostics)
            raise SealVerificationError(f"seal violation: {details}")
        seal_path = self.package_dir / "contracts" / "package_contract.json"
        return json.loads(seal_path.read_text())["executable_fingerprint"]

    def _load_module(self) -> ModuleType:
        self.link_root.mkdir(parents=True, exist_ok=True)
        link = self.link_root / self.package_name
        if not link.exists():
            link.symlink_to(self.package_dir, target_is_directory=True)
        if str(self.link_root) not in sys.path:
            sys.path.insert(0, str(self.link_root))
        return importlib.import_module(self.package_name)
