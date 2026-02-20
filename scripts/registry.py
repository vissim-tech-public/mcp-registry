#!/usr/bin/env python3
"""MCP Registry Template CLI - validate and compile registry configurations."""

import argparse
import json
import sys
from pathlib import Path

# Project root (parent of scripts/)
ROOT_DIR = Path(__file__).parent.parent
DEFAULT_REGISTRY_NAME = "io.modelcontextprotocol.registry/private"

def load_config() -> dict:
    """Load config.json with defaults."""
    config_path = ROOT_DIR / "config.json"
    defaults = {
        "output": "dist/registry.json",
        "fetchTimeout": 30,
        "registryName": "io.modelcontextprotocol.registry/publisher-provided",
    }
    if config_path.exists():
        with open(config_path) as f:
            user_config = json.load(f)
            defaults.update(user_config)
    return defaults


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate registry.json and all server definitions."""
    from scripts.validator import validate_all

    result = validate_all(ROOT_DIR)

    if args.json:
        output = {
            "valid": result.is_valid,
            "errors": [
                {"file": e.file, "path": e.path, "message": e.message}
                for e in result.errors
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        if result.is_valid:
            if not args.quiet:
                print("All validations passed")
        else:
            for error in result.errors:
                print(f"Error: {error}")

    return 0 if result.is_valid else 1


def cmd_compile(args: argparse.Namespace) -> int:
    """Fetch public registries, merge with private, output compiled registry."""
    from scripts.compiler import compile_registry, write_compiled_registry
    from scripts.validator import validate_all

    # First validate
    validation = validate_all(ROOT_DIR)
    if not validation.is_valid:
        if args.json:
            print(json.dumps({
                "success": False,
                "stage": "validation",
                "errors": [str(e) for e in validation.errors],
            }, indent=2))
        else:
            print("Validation failed:")
            for error in validation.errors:
                print(f"  Error: {error}")
        return 1

    # Load configs
    config = load_config()
    with open(ROOT_DIR / "registry.json") as f:
        registry_config = json.load(f)

    if not args.quiet:
        print("Compiling registry...")

    # Compile
    result = compile_registry(
        registry_config,
        ROOT_DIR,
        timeout=config.get("fetchTimeout", 30),
    )

    if not result.is_success:
        if args.json:
            print(json.dumps({
                "success": False,
                "stage": "compilation",
                "errors": [e.message for e in result.errors],
            }, indent=2))
        else:
            print("Compilation failed:")
            for error in result.errors:
                print(f"  Error: {error.message}")
        return 1

    # Write output
    output_path = ROOT_DIR / config.get("output", "dist/registry.json")

    registry_name = config.get("registryName", DEFAULT_REGISTRY_NAME)
    write_compiled_registry(result.servers, output_path, registry_name)

    if args.json:
        print(json.dumps({
            "success": True,
            "servers": len(result.servers),
            "output": str(output_path),
        }, indent=2))
    elif not args.quiet:
        print(f"Compiled {len(result.servers)} servers to {output_path}")

    return 0


def cmd_add(args: argparse.Namespace) -> int:
    """Add a new private MCP server."""
    from scripts.adder import add_server

    # Load config for registry name
    config = load_config()

    # Parse url_or_command based on transport type
    url_or_cmd = args.url_or_command
    # Remove leading '--' if present (argparse.REMAINDER keeps it)
    if url_or_cmd and url_or_cmd[0] == "--":
        url_or_cmd = url_or_cmd[1:]

    if args.transport in ("sse", "streamable-http"):
        url = url_or_cmd[0] if url_or_cmd else None
        command = []
    else:  # stdio
        url = None
        command = url_or_cmd

    result = add_server(
        name=args.name,
        transport=args.transport,
        url=url,
        command=command,
        description=args.description,
        env_vars=args.env,
        root_dir=ROOT_DIR,
        quiet=args.quiet,
        json_output=args.json,
        registry_name=config.get("registryName"),
    )
    return 0 if result.success else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mcp-registry",
        description="MCP Registry Template - validate and compile registry configurations",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Only show errors"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output in JSON format (for CI)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate registry.json and server definitions"
    )
    validate_parser.set_defaults(func=cmd_validate)

    # compile command
    compile_parser = subparsers.add_parser(
        "compile", help="Compile registry from public + private sources"
    )
    compile_parser.set_defaults(func=cmd_compile)

    # add command
    add_parser = subparsers.add_parser(
        "add", help="Add a new private MCP server"
    )
    add_parser.add_argument(
        "--transport", "-t",
        required=True,
        choices=["stdio", "sse", "streamable-http"],
        help="Transport type",
    )
    add_parser.add_argument(
        "name",
        help="Server name in author/name format",
    )
    add_parser.add_argument(
        "url_or_command",
        nargs=argparse.REMAINDER,
        help="URL for sse/streamable-http, or command after -- for stdio",
    )
    add_parser.add_argument(
        "--description", "-d",
        default="",
        help="Server description",
    )
    add_parser.add_argument(
        "--env", "-e",
        action="append",
        default=[],
        help="Environment variable (KEY or KEY=default)",
    )
    add_parser.set_defaults(func=cmd_add)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
