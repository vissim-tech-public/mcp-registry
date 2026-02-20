"""Tests for add command."""

import json

import pytest

from scripts.adder import (
    EnvVar,
    add_server,
    build_package_from_command,
    build_remote_server,
    parse_env_var,
    parse_name,
)


class TestParseName:
    """Tests for parse_name function."""

    def test_valid_name(self):
        """Given valid author/name, returns tuple."""
        assert parse_name("anthropic/github") == ("anthropic", "github")

    def test_name_with_dots(self):
        """Given name with dots, parses correctly."""
        assert parse_name("com.example/my-server") == ("com.example", "my-server")

    def test_missing_slash_raises(self):
        """Given name without slash, raises ValueError."""
        with pytest.raises(ValueError, match="author/name"):
            parse_name("noauthor")

    def test_empty_parts_raises(self):
        """Given empty author or name, raises ValueError."""
        with pytest.raises(ValueError):
            parse_name("/noauthor")
        with pytest.raises(ValueError):
            parse_name("noname/")


class TestParseEnvVar:
    """Tests for parse_env_var function."""

    def test_name_only(self):
        """Given KEY, returns EnvVar with no default."""
        ev = parse_env_var("API_KEY")
        assert ev.name == "API_KEY"
        assert ev.default is None

    def test_with_default(self):
        """Given KEY=value, returns EnvVar with default."""
        ev = parse_env_var("DEBUG=false")
        assert ev.name == "DEBUG"
        assert ev.default == "false"

    def test_empty_default(self):
        """Given KEY=, returns EnvVar with empty string default."""
        ev = parse_env_var("EMPTY=")
        assert ev.name == "EMPTY"
        assert ev.default == ""


class TestBuildRemoteServer:
    """Tests for build_remote_server function."""

    def test_sse_server(self):
        """Given SSE transport, builds correct structure."""
        result = build_remote_server(
            name="test/server",
            transport="sse",
            url="https://example.com/sse",
            description="Test server",
        )
        assert result["name"] == "test/server"
        assert result["remotes"][0]["type"] == "sse"
        assert result["remotes"][0]["url"] == "https://example.com/sse"

    def test_default_description(self):
        """Given empty description, uses default."""
        result = build_remote_server("x/y", "sse", "https://x.com", "")
        assert "x/y" in result["description"]


class TestBuildPackageFromCommand:
    """Tests for build_package_from_command function."""

    def test_npx_command(self):
        """Given npx command, detects npm registry."""
        pkg = build_package_from_command(["npx", "-y", "@org/pkg"], [])
        assert pkg["registryType"] == "npm"
        assert pkg["identifier"] == "@org/pkg"

    def test_uvx_command(self):
        """Given uvx command, detects pypi registry."""
        pkg = build_package_from_command(["uvx", "my-package"], [])
        assert pkg["registryType"] == "pypi"
        assert pkg["identifier"] == "my-package"

    def test_env_vars_added(self):
        """Given env vars, includes in package."""
        pkg = build_package_from_command(
            ["npx", "pkg"],
            [EnvVar("KEY"), EnvVar("DEBUG", "false")],
        )
        env = pkg["environmentVariables"]
        assert len(env) == 2
        assert env[0]["name"] == "KEY"
        assert env[1]["default"] == "false"


class TestAddServer:
    """Integration tests for add_server function."""

    def test_add_remote_server(self, tmp_path):
        """Given remote server args, creates server.json and updates registry."""
        # Setup
        registry = {
            "registries": [
                {"name": "private", "type": "private", "servers_relative_path": []}
            ]
        }
        (tmp_path / "registry.json").write_text(json.dumps(registry))
        (tmp_path / "mcps").mkdir()

        # Execute
        result = add_server(
            name="test/myserver",
            transport="sse",
            url="https://example.com/sse",
            command=[],
            description="Test",
            env_vars=[],
            root_dir=tmp_path,
            quiet=True,
        )

        # Verify
        assert result.success
        server_path = tmp_path / "mcps/test/myserver/server.json"
        assert server_path.exists()

        server = json.loads(server_path.read_text())
        assert server["remotes"][0]["url"] == "https://example.com/sse"

        updated_registry = json.loads((tmp_path / "registry.json").read_text())
        paths = updated_registry["registries"][0]["servers_relative_path"]
        assert "mcps/test/myserver/server.json" in paths

    def test_add_stdio_server(self, tmp_path):
        """Given stdio server args, creates package-based server.json."""
        registry = {
            "registries": [
                {"name": "private", "type": "private", "servers_relative_path": []}
            ]
        }
        (tmp_path / "registry.json").write_text(json.dumps(registry))
        (tmp_path / "mcps").mkdir()

        result = add_server(
            name="test/npxserver",
            transport="stdio",
            url=None,
            command=["npx", "-y", "@anthropic/mcp"],
            description="NPX server",
            env_vars=["API_KEY", "DEBUG=false"],
            root_dir=tmp_path,
            quiet=True,
        )

        assert result.success
        server = json.loads((tmp_path / "mcps/test/npxserver/server.json").read_text())
        assert server["packages"][0]["registryType"] == "npm"
        assert len(server["packages"][0]["environmentVariables"]) == 2

    def test_missing_url_for_remote(self, tmp_path):
        """Given remote transport without URL, returns error."""
        result = add_server(
            name="test/x",
            transport="sse",
            url=None,
            command=[],
            description="",
            env_vars=[],
            root_dir=tmp_path,
        )
        assert not result.success
        assert "URL required" in result.message

    def test_missing_command_for_stdio(self, tmp_path):
        """Given stdio transport without command, returns error."""
        result = add_server(
            name="test/x",
            transport="stdio",
            url=None,
            command=[],
            description="",
            env_vars=[],
            root_dir=tmp_path,
        )
        assert not result.success
        assert "Command required" in result.message
