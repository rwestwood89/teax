"""Unit tests for field reference parsing in pipeline schema."""
import pytest
from simkit.config.pipeline_schema import _parse_inputs, ChannelSource


def test_parse_field_reference_single_level():
    """Parse 'Type channel.field' correctly into binding."""
    raw = {"blanket": "BlanketConfig fusion_params.blanket_config"}
    bindings = _parse_inputs(raw)

    assert bindings["blanket"].channel_name == "fusion_params"
    assert bindings["blanket"].field_path == "blanket_config"
    assert bindings["blanket"].type_name == "BlanketConfig"
    assert bindings["blanket"].is_field_reference is True
    assert bindings["blanket"].source is ChannelSource.MODULE


def test_parse_field_reference_rejects_nested():
    """Reject nested field paths in Phase 1."""
    raw = {"temp": "FloatValue fusion_params.blanket.temperature"}

    with pytest.raises(ValueError, match="Nested field paths not supported"):
        _parse_inputs(raw)


def test_parse_standard_binding_unchanged():
    """Ensure 'Type channel' still works without field path."""
    raw = {"geo": "Geography geo"}
    bindings = _parse_inputs(raw)

    assert bindings["geo"].channel_name == "geo"
    assert bindings["geo"].field_path is None
    assert bindings["geo"].is_field_reference is False


def test_parse_field_reference_empty_field_rejected():
    """Reject empty field path like 'Type channel.'"""
    raw = {"blanket": "BlanketConfig fusion_params."}

    with pytest.raises(ValueError, match="Field path cannot be empty"):
        _parse_inputs(raw)


def test_parse_default_binding_unchanged():
    """Default bindings still work with None -> syntax."""
    raw = {"design_prefs": "None -> design_pref_default"}
    bindings = _parse_inputs(raw)

    assert bindings["design_prefs"].source is ChannelSource.DEFAULT
    assert bindings["design_prefs"].field_path is None


def test_parse_multiple_bindings_mixed():
    """Mix of standard, field reference, and default bindings."""
    raw = {
        "geo": "Geography geo",
        "blanket": "BlanketConfig fusion_params.blanket_config",
        "design_prefs": "None -> design_pref_default"
    }
    bindings = _parse_inputs(raw)

    assert not bindings["geo"].is_field_reference
    assert bindings["blanket"].is_field_reference
    assert bindings["design_prefs"].is_default
