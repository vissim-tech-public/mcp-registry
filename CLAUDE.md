# CLAUDE.md

## Repository Overview

Git-based template for MCP (Model Context Protocol) server registries. Organizations clone this to control which MCP servers their developers can install — combining curated selections from public registries with internal/private servers.

## Adding a New MCP Server

### From a public registry

1. Browse [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io) or [api.mcp.github.com](https://api.mcp.github.com)
2. Add the server name + version to `registry.json` under the appropriate registry entry:
   ```json
   {"author/server-name": "latest"}
   ```
3. Run `python scripts/registry.py validate` to verify

### As a private server (remote/SSE)

```bash
python scripts/registry.py add -t sse author/name https://your-server.com/mcp/sse
```

This creates `mcps/author/name/server.json` and updates `registry.json` automatically.

### As a private server (stdio/npm/pip)

```bash
python scripts/registry.py add -t stdio author/name -- npx -y @some-org/mcp-server
```

### Finding MCPs

- Official registry: `https://registry.modelcontextprotocol.io/v0.1/servers`
- GitHub/VSCode registry: `https://api.mcp.github.com/v0.1/servers`
- Browse at [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io)

## Validation

```bash
python scripts/registry.py validate          # check all configs + schemas
python scripts/registry.py --json validate   # JSON output for CI
python scripts/registry.py compile           # fetch public + merge private → dist/registry.json
pytest tests/ -v                             # run tests
```

Validation checks: `registry.json` against `schemas/registry.schema.json`, `config.json` against `schemas/config.schema.json`, and each private `server.json` against its declared `$schema` URL.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

## Project Structure

```
registry.json                      # Which servers to include (user-owned)
config.json                        # Local settings (user-owned)
mcps/{author}/{name}/server.json   # Private server definitions (user-owned)
scripts/                           # CLI: registry.py, validator.py, fetcher.py, compiler.py, adder.py
schemas/                           # JSON schemas for validation
dist/registry.json                 # Compiled output
```
