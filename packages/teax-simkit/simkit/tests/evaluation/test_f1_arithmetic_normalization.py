"""Generated F1 arithmetic normalization across both evaluator backends."""
from __future__ import annotations

import hashlib
import json
import traceback
from pathlib import Path

import pytest

from simkit.core.pipeline_executor import PipelineExecutionContext
from simkit.evaluation import EvaluationFailed, EvaluationFailure, EvaluationPhase
from simkit.evaluation.evaluator import FileBackedEvaluator, PreparedEvaluator
from simkit.evaluation.package_load import ProvisionalPackageLoader

F1_ROOT = Path(__file__).parent / "fixtures" / "f1_arithmetic"
PACKAGE_DIR = F1_ROOT / "package_live"
CASES_DIR = F1_ROOT / "cases"
SPEC_PATH = PACKAGE_DIR / "pipelines" / "pipeline.yaml"
PACKAGE_NAME = "f1_arithmetic_constraints"
ENTRY_CHANNEL = "toy_plant_params"
EXPECTED_MODULE_ORDER = (
    "entry_fusion",
    "f1_division_check",
    "f2_power_check",
    "f3_nested_check",
    "constraint_report_aggregator",
    "exit_point",
)

ARITHMETIC_CASES = (
    (
        "division_by_zero",
        ZeroDivisionError,
        "float division by zero",
        "f1_division_check",
    ),
    (
        "zero_negative_power",
        ZeroDivisionError,
        "0.0 cannot be raised to a negative power",
        "f2_power_check",
    ),
    (
        "exponent_overflow",
        OverflowError,
        "(34, 'Numerical result out of range')",
        "f2_power_check",
    ),
    (
        "nested_division",
        ZeroDivisionError,
        "float division by zero",
        "f3_nested_check",
    ),
)

SAFE_CASES = (
    (
        "safe_satisfied",
        {
            "f1_division_check": "satisfied",
            "f2_power_check": "satisfied",
            "f3_nested_check": "satisfied",
            "headline": "satisfied",
        },
    ),
    (
        "safe_violated",
        {
            "f1_division_check": "violated",
            "f2_power_check": "satisfied",
            "f3_nested_check": "satisfied",
            "headline": "violated",
        },
    ),
    (
        "nonfinite_indeterminate",
        {
            "f1_division_check": "indeterminate",
            "f2_power_check": "satisfied",
            "f3_nested_check": "satisfied",
            "headline": "indeterminate",
        },
    ),
)


def _tree_manifest(root: Path) -> tuple:
    if not root.exists() and not root.is_symlink():
        return ("absent",)
    entries = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append((relative, "symlink", str(path.readlink())))
        elif path.is_dir():
            entries.append((relative, "directory"))
        elif path.is_file():
            entries.append((relative, "file", hashlib.sha256(path.read_bytes()).hexdigest()))
        else:  # pragma: no cover - closed fixture trees contain no other kinds
            entries.append((relative, "other"))
    return tuple(entries)


def _evaluators(tmp_path: Path):
    loader = ProvisionalPackageLoader(
        package_dir=PACKAGE_DIR,
        package_name=PACKAGE_NAME,
        link_root=tmp_path / "links",
    )
    prepared = PreparedEvaluator(loader, SPEC_PATH, expects_constraint_report=True)
    output_root = tmp_path / "candidate-output"
    work_root = tmp_path / "scratch"
    file_backed = FileBackedEvaluator(
        loader, PACKAGE_DIR, work_root, output_root, expects_constraint_report=True
    )
    return prepared, file_backed, work_root, output_root


def _prepared_input(evaluator: PreparedEvaluator, case_path: Path):
    raw = json.loads(case_path.read_text(encoding="utf-8"))
    return {ENTRY_CHANNEL: evaluator.entry_models[ENTRY_CHANNEL](**raw)}


def _capture_prepared(evaluator: PreparedEvaluator, case_path: Path) -> EvaluationFailed:
    with pytest.raises(EvaluationFailed) as caught:
        evaluator.evaluate(_prepared_input(evaluator, case_path))
    return caught.value


def _capture_file(evaluator: FileBackedEvaluator, case_path: Path) -> EvaluationFailed:
    with pytest.raises(EvaluationFailed) as caught:
        evaluator.evaluate(case_path)
    return caught.value


@pytest.mark.parametrize(
    "case_name,error_type,message,module_key",
    ARITHMETIC_CASES,
    ids=[row[0] for row in ARITHMETIC_CASES],
)
def test_both_backends_normalize_native_arithmetic_failure(
    tmp_path, case_name, error_type, message, module_key
):
    prepared, file_backed, work_root, output_root = _evaluators(tmp_path)
    case_path = CASES_DIR / f"{case_name}.json"
    work_before = _tree_manifest(work_root)
    output_before = _tree_manifest(output_root)

    prepared_error = _capture_prepared(prepared, case_path)
    file_error = _capture_file(file_backed, case_path)

    expected = EvaluationFailure(
        phase=EvaluationPhase.MODULE_EXECUTION,
        module_or_channel=module_key,
        cause=f"{error_type.__name__}: {message}",
    )
    assert prepared_error.failure == file_error.failure == expected
    for normalized in (prepared_error, file_error):
        cause = normalized.__cause__
        assert type(cause) is error_type
        assert str(cause) == message
        assert cause.__cause__ is None
        traceback_paths = [frame.filename for frame in traceback.extract_tb(cause.__traceback__)]
        assert any(
            path.endswith("modules/constraints/predicates.py") for path in traceback_paths
        )
        assert any("constraintmodule.py" in path for path in traceback_paths)

    assert output_before == _tree_manifest(output_root) == ("absent",)
    work_after = _tree_manifest(work_root)
    expected_entry = (
        "inputs/toy_plant_params.json",
        "file",
        hashlib.sha256(case_path.read_bytes()).hexdigest(),
    )
    assert set(work_after) == set(work_before) | {expected_entry}
    assert file_backed._entry_path.read_bytes() == case_path.read_bytes()


@pytest.mark.parametrize(
    "case_name,earlier_channels,failed_channel",
    (
        (
            "zero_negative_power",
            ("f1_division_check__evaluation",),
            "f2_power_check__evaluation",
        ),
        (
            "nested_division",
            (
                "f1_division_check__evaluation",
                "f2_power_check__evaluation",
            ),
            "f3_nested_check__evaluation",
        ),
    ),
)
def test_later_failure_keeps_earlier_work_internal_without_aggregate(
    tmp_path, case_name, earlier_channels, failed_channel
):
    _, evaluator, _, _ = _evaluators(tmp_path)
    case_path = CASES_DIR / f"{case_name}.json"
    evaluator._entry_path.write_bytes(case_path.read_bytes())
    context = PipelineExecutionContext(evaluator._registry)
    assert tuple(evaluator._graph.topological_order) == EXPECTED_MODULE_ORDER

    with pytest.raises((ZeroDivisionError, OverflowError)):
        evaluator._executor.run(evaluator._graph, context, persist_outputs=False)

    for channel in earlier_channels:
        assert channel in context.channels
    assert failed_channel not in context.channels
    assert "constraint_report" not in context.channels


@pytest.mark.parametrize(
    "case_name,expected_responses", SAFE_CASES, ids=[row[0] for row in SAFE_CASES]
)
def test_safe_and_nonfinite_cases_preserve_cross_backend_evidence(
    tmp_path, case_name, expected_responses
):
    prepared, file_backed, _, _ = _evaluators(tmp_path)
    case_path = CASES_DIR / f"{case_name}.json"

    prepared_evidence = prepared.evaluate(_prepared_input(prepared, case_path))
    file_evidence = file_backed.evaluate(case_path)

    assert prepared_evidence.responses == file_evidence.responses == expected_responses
    assert prepared_evidence.outputs == file_evidence.outputs
