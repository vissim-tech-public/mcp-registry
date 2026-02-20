"""Tests for validation logic using BDD style (Given-When-Then)."""

import json
import tempfile
from pathlib import Path

import pytest

from scripts.validator import (
    ValidationResult,
    validate_config,
    validate_registry,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory with schema files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create schemas directory
        schemas_dir = tmppath / "schemas"
        schemas_dir.mkdir()

        # Copy schema content (simplified for test)
        config_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "output": {"type": "string"},
                "fetchTimeout": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        }
        with open(schemas_dir / "config.schema.json", "w") as f:
            json.dump(config_schema, f)

        registry_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["registries"],
            "properties": {
                "registries": {"type": "array"},
            },
        }
        with open(schemas_dir / "registry.schema.json", "w") as f:
            json.dump(registry_schema, f)

        yield tmppath


class TestValidateConfig:
    """Tests for config.json validation."""

    def test_valid_config_passes_validation(self, temp_dir):
        """
        Given a valid config.json with correct types
        When validate_config is called
        Then it should return a valid result with no errors
        """
        # Given
        config = {"output": "dist/registry.json", "fetchTimeout": 30}
        config_path = temp_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f)

        # When
        result = validate_config(
            config_path,
            temp_dir / "schemas" / "config.schema.json",
        )

        # Then
        assert result.is_valid
        assert len(result.errors) == 0

    def test_invalid_type_fails_validation(self, temp_dir):
        """
        Given a config.json with fetchTimeout as string instead of integer
        When validate_config is called
        Then it should return an invalid result with type error
        """
        # Given
        config = {"output": "dist/registry.json", "fetchTimeout": "not-a-number"}
        config_path = temp_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f)

        # When
        result = validate_config(
            config_path,
            temp_dir / "schemas" / "config.schema.json",
        )

        # Then
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].path == "fetchTimeout"

    def test_missing_config_file_is_acceptable(self, temp_dir):
        """
        Given config.json does not exist
        When validate_config is called
        Then it should return a valid result (config is optional)
        """
        # Given
        config_path = temp_dir / "config.json"  # Does not exist

        # When
        result = validate_config(
            config_path,
            temp_dir / "schemas" / "config.schema.json",
        )

        # Then
        assert result.is_valid

    def test_malformed_json_fails_validation(self, temp_dir):
        """
        Given a config.json with invalid JSON syntax
        When validate_config is called
        Then it should return an invalid result with parse error
        """
        # Given
        config_path = temp_dir / "config.json"
        with open(config_path, "w") as f:
            f.write("{invalid json}")

        # When
        result = validate_config(
            config_path,
            temp_dir / "schemas" / "config.schema.json",
        )

        # Then
        assert not result.is_valid
        assert any("Invalid JSON" in e.message for e in result.errors)


class TestValidateRegistry:
    """Tests for registry.json validation."""

    def test_missing_required_field_fails_validation(self, temp_dir):
        """
        Given a registry.json without required 'registries' field
        When validate_registry is called
        Then it should return an invalid result with missing field error
        """
        # Given
        registry = {}  # Missing 'registries'
        registry_path = temp_dir / "registry.json"
        with open(registry_path, "w") as f:
            json.dump(registry, f)

        # When
        result = validate_registry(
            registry_path,
            temp_dir / "schemas" / "registry.schema.json",
        )

        # Then
        assert not result.is_valid
        assert any("registries" in e.message for e in result.errors)

    def test_valid_registry_passes_validation(self, temp_dir):
        """
        Given a registry.json with required 'registries' array
        When validate_registry is called
        Then it should return a valid result
        """
        # Given
        registry = {"registries": []}
        registry_path = temp_dir / "registry.json"
        with open(registry_path, "w") as f:
            json.dump(registry, f)

        # When
        result = validate_registry(
            registry_path,
            temp_dir / "schemas" / "registry.schema.json",
        )

        # Then
        assert result.is_valid

    def test_missing_registry_file_fails_validation(self, temp_dir):
        """
        Given registry.json does not exist
        When validate_registry is called
        Then it should return an invalid result with file not found error
        """
        # Given
        registry_path = temp_dir / "registry.json"  # Does not exist

        # When
        result = validate_registry(
            registry_path,
            temp_dir / "schemas" / "registry.schema.json",
        )

        # Then
        assert not result.is_valid
        assert any("not found" in e.message.lower() for e in result.errors)


class TestValidationResult:
    """Tests for ValidationResult behavior."""

    def test_empty_result_is_valid(self):
        """
        Given a new ValidationResult with no errors
        When is_valid is checked
        Then it should return True
        """
        # Given
        result = ValidationResult()

        # When/Then
        assert result.is_valid

    def test_result_with_errors_is_invalid(self):
        """
        Given a ValidationResult with added errors
        When is_valid is checked
        Then it should return False
        """
        # Given
        result = ValidationResult()
        result.add_error("file.json", "path", "error message")

        # When/Then
        assert not result.is_valid

    def test_merge_combines_errors(self):
        """
        Given two ValidationResults with different errors
        When merge is called
        Then the result should contain all errors from both
        """
        # Given
        result1 = ValidationResult()
        result1.add_error("file1.json", "", "error 1")
        result2 = ValidationResult()
        result2.add_error("file2.json", "", "error 2")

        # When
        result1.merge(result2)

        # Then
        assert len(result1.errors) == 2
