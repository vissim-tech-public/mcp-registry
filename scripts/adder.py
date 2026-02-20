"""Add command implementation - creates private MCP server definitions."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AddResult:
    """Result of add operation."""
    success: bool
    server_path: Path | None = None
    message: str = ""


@dataclass
class EnvVar:
    """Parsed environment variable."""
    name: str
    default: str | None = None


def parse_name(name: str) -> tuple[str, str]:
    """Parse 'author/name' into (author, name). Raises ValueError if invalid."""
    if "/" not in name:
        raise ValueError(f"Name must be in 'author/name' format, got: {name}")
    parts = name.split("/", 1)
    author, server_name = parts[0].strip(), parts[1].strip()
    if not author or not server_name:
        raise ValueError(f"Both author and name required, got: {name}")
    return author, server_name


def parse_env_var(env_str: str) -> EnvVar:
    """Parse 'KEY' or 'KEY=default' into EnvVar."""
    if "=" in env_str:
        name, default = env_str.split("=", 1)
        return EnvVar(name=name.strip(), default=default)
    return EnvVar(name=env_str.strip())


def build_remote_server(
    name: str,
    transport: str,
    url: str,
    description: str,
) -> dict:
    """Build server.json content for remote (sse/streamable-http) server."""
    return {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json",
        "name": name,
        "description": description or f"Private MCP server: {name}",
        "version": "1.0.0",
        "remotes": [
            {"type": transport, "url": url}
        ],
    }


def build_stdio_server(
    name: str,
    command: list[str],
    description: str,
    env_vars: list[EnvVar],
) -> dict:
    """Build server.json content for stdio server."""
    package = build_package_from_command(command, env_vars)

    return {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json",
        "name": name,
        "description": description or f"Private MCP server: {name}",
        "version": "1.0.0",
        "packages": [package],
    }


def build_package_from_command(command: list[str], env_vars: list[EnvVar]) -> dict:
    """Build package definition from command list."""
    if not command:
        raise ValueError("Command required for stdio transport")

    package: dict = {
        "transport": {"type": "stdio"},
        "version": "1.0.0",
    }

    # Detect registry type and identifier from command
    cmd = command[0].lower()
    args = command[1:] if len(command) > 1 else []

    if cmd == "npx":
        package["registryType"] = "npm"
        # Find package identifier (skip flags like -y)
        for arg in args:
            if not arg.startswith("-"):
                package["identifier"] = arg
                break
    elif cmd == "uvx" or (cmd == "python" and "-m" in args):
        package["registryType"] = "pypi"
        # For uvx: first non-flag arg; for python -m: arg after -m
        if cmd == "uvx":
            for arg in args:
                if not arg.startswith("-"):
                    package["identifier"] = arg
                    break
        else:
            try:
                m_idx = args.index("-m")
                if m_idx + 1 < len(args):
                    package["identifier"] = args[m_idx + 1]
            except ValueError:
                pass

    # Fallback: store command as identifier if we couldn't detect
    if "identifier" not in package:
        package["registryType"] = "npm"  # default
        package["identifier"] = " ".join(command)

    # Add environment variables
    if env_vars:
        package["environmentVariables"] = [
            {"name": ev.name, "isRequired": False}
            | ({"default": ev.default} if ev.default is not None else {})
            for ev in env_vars
        ]

    return package


def add_to_registry(registry_path: Path, server_relative_path: str) -> None:
    """Add server path to registry.json's private registry."""
    with open(registry_path) as f:
        registry = json.load(f)

    # Find private registry entry
    private_reg = None
    for reg in registry.get("registries", []):
        if reg.get("type") == "private":
            private_reg = reg
            break

    if private_reg is None:
        # Create private registry entry
        private_reg = {
            "name": "private",
            "type": "private",
            "servers_relative_path": [],
        }
        registry.setdefault("registries", []).append(private_reg)

    # Add path if not already present
    paths = private_reg.setdefault("servers_relative_path", [])
    if server_relative_path not in paths:
        paths.append(server_relative_path)

    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=4)
        f.write("\n")


def add_server(
    name: str,
    transport: str,
    url: str | None,
    command: list[str],
    description: str,
    env_vars: list[str],
    root_dir: Path,
    quiet: bool = False,
    json_output: bool = False,
) -> AddResult:
    """Main entry point for add command."""
    try:
        # Parse and validate
        author, server_name = parse_name(name)
        parsed_env = [parse_env_var(e) for e in env_vars]

        # Validate transport-specific requirements
        if transport in ("sse", "streamable-http"):
            if not url:
                return AddResult(False, message=f"URL required for {transport} transport")
            server_data = build_remote_server(name, transport, url, description)
        else:  # stdio
            if not command:
                msg = "Command required for stdio transport (use -- before command)"
                return AddResult(False, message=msg)
            server_data = build_stdio_server(name, command, description, parsed_env)

        # Create directory and file
        server_dir = root_dir / "mcps" / author / server_name
        server_dir.mkdir(parents=True, exist_ok=True)
        server_path = server_dir / "server.json"

        with open(server_path, "w") as f:
            json.dump(server_data, f, indent=4)
            f.write("\n")

        # Update registry.json
        relative_path = f"mcps/{author}/{server_name}/server.json"
        registry_path = root_dir / "registry.json"
        if registry_path.exists():
            add_to_registry(registry_path, relative_path)

        # Output
        if json_output:
            import sys
            json.dump({
                "success": True,
                "path": str(server_path),
                "name": name,
            }, sys.stdout, indent=2)
            print()
        elif not quiet:
            print(f"Created {server_path}")
            print("Added to registry.json")

        return AddResult(True, server_path=server_path)

    except ValueError as e:
        return AddResult(False, message=str(e))
    except Exception as e:
        return AddResult(False, message=f"Failed to add server: {e}")
