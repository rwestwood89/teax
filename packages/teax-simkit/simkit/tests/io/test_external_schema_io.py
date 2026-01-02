"""Tests for I/O operations with external BaseModel schemas."""
import json
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from simkit.io import readers
from simkit.core.pipeline_executor import _BUILTIN_ENTRY_LOADERS


class ExternalSchema(BaseModel):
    """External schema using plain BaseModel, not StrictBaseModel."""
    name: str
    value: float
    metadata: dict = Field(default_factory=dict)


def test_read_json_model_accepts_external_basemodel(tmp_path):
    """Test that readers.read_json_model accepts any BaseModel subclass."""
    # Create test JSON file
    test_data = {
        "name": "test_item",
        "value": 42.5,
        "metadata": {"source": "external"}
    }

    json_file = tmp_path / "external_data.json"
    json_file.write_text(json.dumps(test_data))

    # Should work with external BaseModel (not StrictBaseModel)
    result = readers.read_json_model(json_file, ExternalSchema)

    assert isinstance(result, ExternalSchema)
    assert result.name == "test_item"
    assert result.value == 42.5
    assert result.metadata == {"source": "external"}


def test_entry_loaders_accepts_external_basemodel(tmp_path):
    """Test that _ENTRY_LOADERS can be extended with external schemas."""
    # Create test JSON file
    test_data = {"name": "entry_test", "value": 123.4, "metadata": {}}
    json_file = tmp_path / "entry_data.json"
    json_file.write_text(json.dumps(test_data))

    # Should be able to register loader for external BaseModel
    _BUILTIN_ENTRY_LOADERS[ExternalSchema] = lambda path: readers.read_json_model(
        path, ExternalSchema
    )

    # Verify registration worked
    assert ExternalSchema in _BUILTIN_ENTRY_LOADERS

    # Verify loader works
    loader = _BUILTIN_ENTRY_LOADERS[ExternalSchema]
    result = loader(json_file)

    assert isinstance(result, ExternalSchema)
    assert result.name == "entry_test"
    assert result.value == 123.4

    # Cleanup
    del _BUILTIN_ENTRY_LOADERS[ExternalSchema]


def test_external_schema_roundtrip(tmp_path):
    """Test writing and reading external schemas."""
    # Create instance
    original = ExternalSchema(
        name="roundtrip_test",
        value=99.9,
        metadata={"key": "value"}
    )

    # Write to JSON
    json_file = tmp_path / "roundtrip.json"
    json_file.write_text(json.dumps(original.model_dump()))

    # Read back
    loaded = readers.read_json_model(json_file, ExternalSchema)

    assert loaded.name == original.name
    assert loaded.value == original.value
    assert loaded.metadata == original.metadata
