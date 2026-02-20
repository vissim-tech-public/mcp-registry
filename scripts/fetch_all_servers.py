#!/usr/bin/env python3
"""
Fetch all MCP servers from the official MCP Registry.

Usage:
    python scripts/fetch_all_servers.py
    python scripts/fetch_all_servers.py --output servers.json
    python scripts/fetch_all_servers.py --limit 50
"""

import argparse
import json
import sys
from typing import Any, Iterator

import requests


REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0.1/servers"


def fetch_all_servers(
    limit_per_page: int = 100,
    timeout: int = 30,
) -> Iterator[dict[str, Any]]:
    """
    Fetch all servers from the MCP registry using cursor-based pagination.
    
    Args:
        limit_per_page: Number of servers to fetch per request (max 100)
        timeout: Request timeout in seconds
        
    Yields:
        Server entries from the registry
    """
    cursor = None
    
    while True:
        params = {"limit": limit_per_page}
        if cursor:
            params["cursor"] = cursor
            
        response = requests.get(REGISTRY_URL, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        
        servers = data.get("servers", [])
        for server in servers:
            yield server
            
        # Check for next page using nextCursor from metadata
        metadata = data.get("metadata", {})
        cursor = metadata.get("nextCursor")
        
        if not cursor:
            break


def main():
    parser = argparse.ArgumentParser(
        description="Fetch all MCP servers from the official registry"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)",
        default=None,
    )
    parser.add_argument(
        "--limit", "-l",
        help="Limit total number of servers to fetch",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--pretty", "-p",
        help="Pretty print JSON output",
        action="store_true",
    )
    parser.add_argument(
        "--names-only", "-n",
        help="Print only server names (one per line)",
        action="store_true",
    )
    args = parser.parse_args()
    
    servers = []
    count = 0
    
    try:
        for server in fetch_all_servers():
            if args.limit and count >= args.limit:
                break
                
            servers.append(server)
            count += 1
            
            # Print progress to stderr
            if count % 100 == 0:
                print(f"Fetched {count} servers...", file=sys.stderr)
                
    except requests.RequestException as e:
        print(f"Error fetching servers: {e}", file=sys.stderr)
        sys.exit(1)
        
    print(f"Total servers fetched: {len(servers)}", file=sys.stderr)
    
    # Format output
    if args.names_only:
        output_lines = []
        for s in servers:
            server_info = s.get("server", {})
            name = server_info.get("name", "unknown")
            version = server_info.get("version", "")
            output_lines.append(f"{name}@{version}" if version else name)
        output = "\n".join(output_lines)
    else:
        indent = 2 if args.pretty else None
        output = json.dumps({"servers": servers, "count": len(servers)}, indent=indent)
    
    # Write output
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
