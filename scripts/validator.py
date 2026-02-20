"""Validation logic for registry configurations and server definitions."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import requests

# Cache for remote schemas
_schema_cache: dict[str, dict] = {}


@dataclass
class ValidationError:
    """A single validation error."""
    file: str
    path: str
    message: str

    def __str__(self) -> str:
        if self.path:
            return f"{self.file}: {self.path}: {self.message}"
        return f"{self.file}: {self.message}"


@dataclass
class ValidationResult:
    """Result of validation containing all errors."""
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, file: str, path: str, message: str) -> None:
        self.errors.append(ValidationError(file, path, message))

    def merge(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)


def load_schema(schema_path: Path) -> dict:
    """Load a JSON schema from a local file."""
    with open(schema_path) as f:
        return json.load(f)


def fetch_remote_schema(url: str, timeout: int = 10) -> dict:
    """Fetch a JSON schema from a URL with caching."""
    if url in _schema_cache:
        return _schema_cache[url]

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    schema = response.json()
    _schema_cache[url] = schema
    return schema


def validate_against_schema(
    data: dict,
    schema: dict,
    file_name: str,
) -> ValidationResult:
    """Validate data against a JSON schema, collecting all errors."""
    result = ValidationResult()
    validator = jsonschema.Draft7Validator(schema)

    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else ""
        result.add_error(file_name, path, error.message)

    return result


def validate_config(config_path: Path, schema_path: Path) -> ValidationResult:
    """Validate config.json against its schema."""
    result = ValidationResult()

    if not config_path.exists():
        # config.json is optional
        return result

    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        result.add_error(str(config_path), "", f"Invalid JSON: {e}")
        return result

    schema = load_schema(schema_path)
    return validate_against_schema(config, schema, str(config_path))


def validate_registry(registry_path: Path, schema_path: Path) -> ValidationResult:
    """Validate registry.json against its schema."""
    result = ValidationResult()

    if not registry_path.exists():
        result.add_error(str(registry_path), "", "File not found")
        return result

    try:
        with open(registry_path) as f:
            registry = json.load(f)
    except json.JSONDecodeError as e:
        result.add_error(str(registry_path), "", f"Invalid JSON: {e}")
        return result

    schema = load_schema(schema_path)
    return validate_against_schema(registry, schema, str(registry_path))


def validate_server_json(
    server_path: Path,
    root_dir: Path,
) -> ValidationResult:
    """Validate a server.json file against its declared schema."""
    result = ValidationResult()
    relative_path = server_path.relative_to(root_dir)

    if not server_path.exists():
        result.add_error(str(relative_path), "", "File not found")
        return result

    try:
        with open(server_path) as f:
            server_data = json.load(f)
    except json.JSONDecodeError as e:
        result.add_error(str(relative_path), "", f"Invalid JSON: {e}")
        return result

    # Get schema URL from $schema field (now at root level)
    schema_url = server_data.get("$schema")
    if not schema_url:
        result.add_error(str(relative_path), "", "Missing '$schema' field")
        return result

    # Fetch and validate against remote schema
    try:
        schema = fetch_remote_schema(schema_url)
        schema_result = validate_against_schema(server_data, schema, str(relative_path))
        result.merge(schema_result)
    except requests.RequestException as e:
        result.add_error(str(relative_path), "$schema", f"Failed to fetch schema: {e}")
    except json.JSONDecodeError as e:
        result.add_error(str(relative_path), "$schema", f"Invalid schema JSON: {e}")

    return result


def validate_all(root_dir: Path) -> ValidationResult:
    """Validate all configuration files in the registry."""
    result = ValidationResult()
    schemas_dir = root_dir / "schemas"

    # Validate config.json
    config_result = validate_config(
        root_dir / "config.json",
        schemas_dir / "config.schema.json",
    )
    result.merge(config_result)

    # Validate registry.json
    registry_path = root_dir / "registry.json"
    registry_result = validate_registry(
        registry_path,
        schemas_dir / "registry.schema.json",
    )
    result.merge(registry_result)

    # If registry.json is invalid, skip server validation
    if not registry_result.is_valid:
        return result

    # Load registry to find private server paths
    with open(registry_path) as f:
        registry = json.load(f)

    # Validate each private server.json
    for reg in registry.get("registries", []):
        if reg.get("type") == "private":
            for rel_path in reg.get("servers_relative_path", []):
                server_path = root_dir / rel_path
                server_result = validate_server_json(server_path, root_dir)
                result.merge(server_result)

    return result
