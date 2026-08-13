"""End-to-end zero-entry-channel coordinate (Lifecycle Item 9).

The `zero_channel` fixture is a real codegen-generated package whose EntryPoint
declares zero channels (the codegen template emits the module with no inputs;
teax's exactly-one-EntryPoint rule is satisfied). This proves the stock bridge +
evaluator handle the zero shape on a real package — no consumer wrapper, no shim.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from simkit.evaluation.evaluator import PreparedEvaluator
from simkit.evaluation.package_load import ProvisionalPackageLoader
from simkit.study.bridge import CandidateBridge

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "zero_channel" / "package_live"
SPEC_PATH = FIXTURE_DIR / "pipelines" / "pipeline.yaml"


@pytest.fixture(scope="module")
def prepared(tmp_path_factory) -> PreparedEvaluator:
    link_root = tmp_path_factory.mktemp("zero_channel_pkg")
    loader = ProvisionalPackageLoader(
        package_dir=FIXTURE_DIR, package_name="zero_channel", link_root=link_root
    )
    loader.load()
    return PreparedEvaluator(loader, SPEC_PATH, expects_constraint_report=True)


def test_zero_channel_package_has_no_entry_channels(prepared):
    assert dict(prepared.entry_models) == {}


def test_zero_channel_bridge_builds_empty_mapping(prepared):
    bridge = CandidateBridge(prepared.entry_models)
    assert bridge.build({}) == {}


def test_zero_channel_evaluates_end_to_end(prepared):
    """Stock bridge + evaluator on the real zero-entry package: the empty
    mapping validates completely and the package evaluates without a wrapper."""
    bridge = CandidateBridge(prepared.entry_models)
    evidence = prepared.evaluate(bridge.build({}))
    assert evidence is not None
