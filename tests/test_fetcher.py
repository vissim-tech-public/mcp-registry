"""Tests for registry fetching using BDD style (Given-When-Then).

Uses real network requests to public registries for integration testing.
"""

from unittest.mock import patch

import pytest
import requests

from scripts.fetcher import (
    FetchError,
    _parse_author_pattern,
    fetch_from_public_registry,
    fetch_server_list,
    fetch_server_version,
)


class TestFetchServerListReal:
    """Tests for fetching server list from real registries."""

    @pytest.mark.timeout(30)
    def test_fetches_servers_from_official_registry(self):
        """
        Given the official MCP registry
        When fetch_server_list is called
        Then it should return servers from the registry
        """
        # Given
        url = "https://api.mcp.github.com/"

        # When
        servers = list(fetch_server_list(url, timeout=10))

        # Then
        assert len(servers) > 0
        # Each server should have server info
        assert all("server" in s for s in servers)


class TestFetchServerVersionReal:
    """Tests for fetching specific server versions from real registries."""

    @pytest.mark.timeout(30)
    def test_fetches_specific_server_from_official_registry(self):
        """
        Given a known server in the official MCP registry
        When fetch_server_version is called with 'latest'
        Then it should return the server data
        """
        # Given
        url = "https://registry.modelcontextprotocol.io"
        server_name = "ai.exa/exa"

        # When
        server_data = fetch_server_version(url, server_name, "latest", timeout=10)

        # Then
        assert "server" in server_data
        assert server_data["server"]["name"] == server_name


class TestFetchFromPublicRegistryReal:
    """Tests for fetching from public registries with various configs."""

    @pytest.mark.timeout(30)
    def test_fetches_specific_servers_from_official_registry(self):
        """
        Given a registry config with specific servers from official registry
        When fetch_from_public_registry is called
        Then it should return those servers
        """
        # Given
        config = {
            "name": "MCP Official",
            "url": "https://registry.modelcontextprotocol.io",
            "servers": {
                "ai.exa/exa": "latest",
            },
        }

        # When
        results = fetch_from_public_registry(config, timeout=10)

        # Then
        assert len(results) == 1
        assert results[0].name == "ai.exa/exa"
        assert results[0].source == "MCP Official"

    @pytest.mark.timeout(30)
    def test_wildcard_with_exclude_from_github_registry(self):
        """
        Given a registry config with wildcard and exclude list for GitHub registry
        When fetch_from_public_registry is called
        Then excluded servers should not be in results
        """
        # Given
        config = {
            "name": "GitHub MCP",
            "url": "https://api.mcp.github.com",
            "servers": "*",
            "exclude": ["microsoft/markitdown"],
        }

        # When
        results = fetch_from_public_registry(config, timeout=15)

        # Then
        assert len(results) > 0
        server_names = [r.name for r in results]
        assert "microsoft/markitdown" not in server_names


class TestFetchErrorHandling:
    """Tests for error handling using mocks."""

    def test_network_error_raises_fetch_error(self):
        """
        Given a registry that fails to respond
        When fetch_from_public_registry is called
        Then it should raise FetchError with registry name
        """
        # Given
        config = {
            "name": "Broken Registry",
            "url": "https://example.com",
            "servers": "*",
        }

        with patch("scripts.fetcher.requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")

            # When/Then
            with pytest.raises(FetchError) as exc_info:
                fetch_from_public_registry(config)

            assert "Broken Registry" in str(exc_info.value)

    def test_http_error_raises_fetch_error(self):
        """
        Given a registry that returns 404
        When fetch_from_public_registry is called
        Then it should raise FetchError
        """
        # Given
        config = {
            "name": "Missing Registry",
            "url": "https://example.com",
            "servers": {"nonexistent/server": "latest"},
        }

        with patch("scripts.fetcher.requests.get") as mock_get:
            response = mock_get.return_value
            response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

            # When/Then
            with pytest.raises(FetchError) as exc_info:
                fetch_from_public_registry(config)

            assert "Missing Registry" in str(exc_info.value)


class TestParseAuthorPattern:
    """Tests for _parse_author_pattern helper."""

    def test_valid_pattern_returns_prefix(self):
        """Given 'microsoft/*', returns 'microsoft/'."""
        assert _parse_author_pattern("microsoft/*") == "microsoft/"

    def test_exact_name_returns_none(self):
        """Given 'ai.exa/exa', returns None."""
        assert _parse_author_pattern("ai.exa/exa") is None

    def test_partial_wildcard_returns_none(self):
        """Given 'micro*/server', returns None (not author/* pattern)."""
        assert _parse_author_pattern("micro*/server") is None


class TestAuthorWildcardPattern:
    """Tests for author/* wildcard pattern support."""

    @pytest.mark.timeout(30)
    def test_author_wildcard_pattern(self):
        """
        Given a registry config with author/* pattern
        When fetch_from_public_registry is called
        Then all servers from that author are returned
        """
        # Given
        config = {
            "name": "GitHub MCP",
            "url": "https://api.mcp.github.com",
            "servers": {"microsoft/*": "latest"},
        }

        # When
        results = fetch_from_public_registry(config, timeout=15)

        # Then
        assert len(results) > 0
        for r in results:
            assert r.name.startswith("microsoft/")

    @pytest.mark.timeout(30)
    def test_mixed_patterns_and_exact(self):
        """
        Given config with both pattern and exact server names
        When fetch_from_public_registry is called
        Then both patterns and exact names are resolved
        """
        # Given - use GitHub registry with microsoft pattern + exact server
        config = {
            "name": "GitHub MCP",
            "url": "https://api.mcp.github.com",
            "servers": {
                "microsoft/*": "latest",
                "microsoft/markitdown": "latest",  # Also matches pattern, tests dedup
            },
        }

        # When
        results = fetch_from_public_registry(config, timeout=15)

        # Then - should have microsoft servers from pattern + exact markitdown
        names = [r.name for r in results]
        assert any(n.startswith("microsoft/") for n in names)
        # markitdown appears in both pattern and exact, should be in results
        assert "microsoft/markitdown" in names
