"""Compile registry from public and private sources."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.fetcher import FetchError, ServerEntry, fetch_from_public_registry


@dataclass
class CompileError:
    """An error during compilation."""
    message: str


@dataclass
class CompileResult:
    """Result of compilation."""
    servers: list[ServerEntry] = field(default_factory=list)
    errors: list[CompileError] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return len(self.errors) == 0


def load_private_server(
    server_path: Path,
    registry_name: str,
    root_dir: Path,
) -> ServerEntry:
    """Load a private server definition from a JSON file."""
    with open(server_path) as f:
        data = json.load(f)

    # Private servers use flattened format (no "server" wrapper)
    return ServerEntry(
        name=data.get("name", ""),
        version=data.get("version", ""),
        data=data,
        source=registry_name,
    )


def check_conflicts(servers: list[ServerEntry]) -> list[CompileError]:
    """Check for duplicate server names and return errors."""
    errors: list[CompileError] = []
    seen: dict[str, ServerEntry] = {}

    for server in servers:
        if server.name in seen:
            existing = seen[server.name]
            # Private vs anything = error
            if server.source == "private" or existing.source == "private":
                errors.append(CompileError(
                    f"Duplicate server '{server.name}': "
                    f"found in '{existing.source}' and '{server.source}'"
                ))
            # Public vs public = last one wins (no error, just skip)
        else:
            seen[server.name] = server

    return errors


def compile_registry(
    registry_config: dict[str, Any],
    root_dir: Path,
    timeout: int = 30,
) -> CompileResult:
    """
    Compile a complete registry from all sources.

    Process order:
    1. Fetch from public registries in order
    2. Load private servers
    3. Check for conflicts
    4. Return merged result
    """
    result = CompileResult()
    all_servers: list[ServerEntry] = []

    for reg in registry_config.get("registries", []):
        if reg.get("type") == "private":
            # Load private servers
            for rel_path in reg.get("servers_relative_path", []):
                server_path = root_dir / rel_path
                try:
                    server = load_private_server(
                        server_path, reg["name"], root_dir
                    )
                    all_servers.append(server)
                except Exception as e:
                    result.errors.append(CompileError(
                        f"Failed to load {rel_path}: {e}"
                    ))
        else:
            # Fetch from public registry
            try:
                servers = fetch_from_public_registry(reg, timeout)
                all_servers.extend(servers)
            except FetchError as e:
                result.errors.append(CompileError(str(e)))
                return result  # Fail fast on fetch errors

    # Check for conflicts
    conflict_errors = check_conflicts(all_servers)
    result.errors.extend(conflict_errors)

    if result.is_success:
        # Deduplicate (last one wins for public-public conflicts)
        seen: dict[str, ServerEntry] = {}
        for server in all_servers:
            seen[server.name] = server
        result.servers = list(seen.values())

    return result


def write_compiled_registry(
    servers: list[ServerEntry],
    output_path: Path,
    registry_name: str = "io.modelcontextprotocol.registry/private",
) -> None:
    """Write the compiled registry to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    def wrap_server(server: ServerEntry) -> dict:
        """Wrap server data in API-compatible format."""
        # Check if data is already wrapped (from public registry)
        if "server" in server.data:
            # Already wrapped (public registry format)
            return {
                **server.data,
                "_source": server.source,
            }
        else:
            # Flattened format (private server) - wrap it
            return {
                "server": server.data,
                "_meta": {
                    registry_name: {
                        "status": "active",
                        "publishedAt": now,
                        "updatedAt": now,
                        "isLatest": True,
                    }
                },
                "_source": server.source,
            }

    output = {
        "servers": [wrap_server(server) for server in servers],
        "metadata": {
            "count": len(servers),
        }
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
