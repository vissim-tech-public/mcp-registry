"""Tests for registry compilation using BDD style (Given-When-Then)."""

import json
import tempfile
from pathlib import Path

import pytest

from scripts.compiler import (
    check_conflicts,
    compile_registry,
    load_private_server,
    write_compiled_registry,
)
from scripts.fetcher import ServerEntry


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_server_entry():
    """Create a sample server entry."""
    return ServerEntry(
        name="test-org/test-server",
        version="1.0.0",
        data={
            "server": {
                "name": "test-org/test-server",
                "version": "1.0.0",
            }
        },
        source="Test Registry",
    )


class TestLoadPrivateServer:
    """Tests for loading private server definitions."""

    def test_loads_server_from_json_file(self, temp_dir):
        """
        Given a valid server.json file in mcps directory
        When load_private_server is called
        Then it should return a ServerEntry with correct data
        """
        # Given - flattened format (no "server" wrapper)
        server_data = {
            "name": "my-org/my-server",
            "version": "0.1.0",
            "description": "Test server",
        }
        mcps_dir = temp_dir / "mcps" / "my-org"
        mcps_dir.mkdir(parents=True)
        server_path = mcps_dir / "server.json"
        with open(server_path, "w") as f:
            json.dump(server_data, f)

        # When
        entry = load_private_server(server_path, "private", temp_dir)

        # Then
        assert entry.name == "my-org/my-server"
        assert entry.version == "0.1.0"
        assert entry.source == "private"


class TestCheckConflicts:
    """Tests for server name conflict detection."""

    def test_no_conflicts_with_unique_names(self):
        """
        Given servers with different names
        When check_conflicts is called
        Then it should return empty error list
        """
        # Given
        servers = [
            ServerEntry("a/server", "1.0", {}, "reg1"),
            ServerEntry("b/server", "1.0", {}, "reg2"),
        ]

        # When
        errors = check_conflicts(servers)

        # Then
        assert len(errors) == 0

    def test_private_public_duplicate_is_error(self):
        """
        Given same server name in private and public registry
        When check_conflicts is called
        Then it should return an error
        """
        # Given
        servers = [
            ServerEntry("a/server", "1.0", {}, "public-reg"),
            ServerEntry("a/server", "1.0", {}, "private"),
        ]

        # When
        errors = check_conflicts(servers)

        # Then
        assert len(errors) == 1
        assert "a/server" in errors[0].message

    def test_public_public_duplicate_allowed(self):
        """
        Given same server name in two public registries
        When check_conflicts is called
        Then it should return no errors (last one wins)
        """
        # Given
        servers = [
            ServerEntry("a/server", "1.0", {}, "reg1"),
            ServerEntry("a/server", "2.0", {}, "reg2"),
        ]

        # When
        errors = check_conflicts(servers)

        # Then
        assert len(errors) == 0


class TestWriteCompiledRegistry:
    """Tests for writing compiled output."""

    def test_writes_servers_with_source_metadata(self, temp_dir, sample_server_entry):
        """
        Given a list of server entries
        When write_compiled_registry is called
        Then it should write JSON with servers and _source metadata
        """
        # Given
        output_path = temp_dir / "dist" / "registry.json"

        # When
        write_compiled_registry([sample_server_entry], output_path)

        # Then
        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert data["metadata"]["count"] == 1
        assert len(data["servers"]) == 1
        assert data["servers"][0]["_source"] == "Test Registry"

    def test_creates_parent_directories(self, temp_dir, sample_server_entry):
        """
        Given an output path with non-existent parent directories
        When write_compiled_registry is called
        Then it should create the directories and write the file
        """
        # Given
        output_path = temp_dir / "deep" / "nested" / "dist" / "registry.json"

        # When
        write_compiled_registry([sample_server_entry], output_path)

        # Then
        assert output_path.exists()


class TestCompileRegistry:
    """Tests for full registry compilation."""

    def test_compiles_private_servers_only(self, temp_dir):
        """
        Given a registry config with only private servers
        When compile_registry is called
        Then it should return those servers in the result
        """
        # Given - flattened format (no "server" wrapper)
        mcps_dir = temp_dir / "mcps" / "org"
        mcps_dir.mkdir(parents=True)
        server_path = mcps_dir / "server.json"
        with open(server_path, "w") as f:
            json.dump({"name": "org/server", "version": "1.0"}, f)

        registry_config = {
            "registries": [
                {
                    "name": "private",
                    "type": "private",
                    "servers_relative_path": ["mcps/org/server.json"],
                }
            ]
        }

        # When
        result = compile_registry(registry_config, temp_dir)

        # Then
        assert result.is_success
        assert len(result.servers) == 1
        assert result.servers[0].name == "org/server"

    def test_fails_on_missing_private_server_file(self, temp_dir):
        """
        Given a registry config referencing non-existent server.json
        When compile_registry is called
        Then it should return an error
        """
        # Given
        registry_config = {
            "registries": [
                {
                    "name": "private",
                    "type": "private",
                    "servers_relative_path": ["mcps/missing/server.json"],
                }
            ]
        }

        # When
        result = compile_registry(registry_config, temp_dir)

        # Then
        assert not result.is_success
        assert len(result.errors) >= 1
