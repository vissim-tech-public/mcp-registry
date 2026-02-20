# Private MCP Registry

A git-based template for managing private MCP (Model Context Protocol) server registries. Organizations clone this to control which MCP servers their developers can install.

## Quick Start (5 minutes, no terminal required)

### 1. Fork or Clone This Repository

Click [Use this template](https://github.com/new?template_name=mcp-registry-template&template_owner=mcp-reg) or fork to your GitHub organization.


### 2. Add an MCP from the Official Registry

Edit `registry.json` to include servers from [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io):

```json
{
    "registries": [
        {
            "name": "MCP Official",
            "url": "https://registry.modelcontextprotocol.io",
            "servers": {
                "ai.exa/exa": "latest"
            }
        }
    ]
}
```

Browse the [MCP Registry](https://registry.modelcontextprotocol.io) to find servers, then add them by name.

### 3. Add a Custom Remote MCP Server

Create a file at `mcps/atlassian/rovo/server.json`:

```json
{
    "$schema": "https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json",
    "name": "atlassian/rovo",
    "description": "Atlassian Rovo MCP Server - access Jira, Confluence, and more",
    "version": "1.0.0",
    "remotes": [
        {
            "type": "sse",
            "url": "https://mcp.atlassian.com/v1/sse"
        }
    ]
}
```

Then add it to `registry.json`:

```json
{
    "registries": [
        {
            "name": "MCP Official",
            "url": "https://registry.modelcontextprotocol.io",
            "servers": {
                "ai.exa/exa": "latest"
            }
        },
        {
            "name": "private",
            "type": "private",
            "servers_relative_path": [
                "mcps/atlassian/rovo/server.json"
            ]
        }
    ]
}
```

### 4. Commit and Push

Commit your changes and push to GitHub. Your registry is now live.

### 5. Configure GitHub Copilot to Use Your Registry

Your registry is served via a proxy service that reads your GitHub repo and exposes it in MCP registry format. No signup required.

**Your registry URL:**
```
https://mcp-private-registry-b08b0.web.app/{org}/{repo}/main/v0.1/servers
```

Replace `{org}` and `{repo}` with your GitHub organization and repository name.

#### For Enterprise/Organization Admins

1. Go to your Enterprise settings → **AI controls** → **MCP**
2. Enable **"MCP servers in Copilot"**
3. Add your registry URL (without the `/v0.1/servers` suffix)
4. Set **"Restrict MCP access to registry servers"** to **"Registry only"** to enforce only approved servers

See [GitHub's MCP configuration docs](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-mcp-usage/configure-mcp-server-access) for detailed instructions.

---

## Understanding the Registry

### registry.json Format

The registry configuration defines which servers to include from public registries and private sources.

#### Public Registry

Fetch servers from public MCP registries like the official registry or GitHub's VSCode registry:

```json
{
    "name": "MCP Official",
    "url": "https://registry.modelcontextprotocol.io",
    "servers": {
        "ai.exa/exa": "latest",
        "some-org/some-server": "1.0.0"
    }
}
```

**Options for `servers`:**
- Specific servers: `{"author/name": "version"}` - include only listed servers
- All servers: `"*"` - include everything from the registry
- With exclusions: Use `"exclude": ["unwanted/server"]` when using `"*"`

#### Private Registry

Reference local server definitions in your `mcps/` folder:

```json
{
    "name": "private",
    "type": "private",
    "servers_relative_path": [
        "mcps/your-org/your-server/server.json"
    ]
}
```

### Available Public Registries

| Registry | URL | Description |
|----------|-----|-------------|
| MCP Official | `https://registry.modelcontextprotocol.io` | Official MCP registry |
| VSCode/GitHub | `https://api.mcp.github.com` | GitHub's MCP registry for VSCode |

---

## Private Server Structure

Private servers live in `mcps/{author}/{name}/server.json`.

### Remote Server (SSE/HTTP)

For servers accessible via URL:

```json
{
    "$schema": "https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json",
    "name": "your-org/your-server",
    "description": "Your server description",
    "version": "1.0.0",
    "remotes": [
        {
            "type": "sse",
            "url": "https://your-server.com/mcp/sse"
        }
    ]
}
```

Transport types: `sse`, `streamable-http`

> **Note on authentication:** If your MCP server requires API keys or auth headers, developers configure those in their local environment (e.g., VS Code settings). The registry only defines *which* servers exist—secrets never go in this repository.

### Package Server (stdio)

For servers installed via npm/pip:

```json
{
    "$schema": "https://static.modelcontextprotocol.io/schemas/2025-09-29/server.schema.json",
    "name": "your-org/your-server",
    "description": "Your server description",
    "version": "1.0.0",
    "packages": [
        {
            "registryType": "npm",
            "identifier": "@your-org/your-server",
            "version": "1.0.0",
            "transport": { "type": "stdio" }
        }
    ]
}
```

---

## CLI Reference (Optional)

For local validation and compilation, install the CLI tools:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
```

### Commands

```bash
# Validate configuration
python scripts/registry.py validate

# Compile registry (fetch public + merge private)
python scripts/registry.py compile

# Add a remote MCP server
python scripts/registry.py add --transport sse atlassian/rovo https://mcp.atlassian.com/v1/sse

# Add a stdio MCP server
python scripts/registry.py add --transport stdio anthropic/everything -- npx -y @anthropic/mcp-server-everything
```

### CLI Options

```bash
python scripts/registry.py --json validate   # JSON output for CI
python scripts/registry.py --quiet compile   # Errors only
```

---

## Configuration

### config.json

Optional local settings:

```json
{
    "output": "dist/registry.json",
    "fetchTimeout": 30
}
```

---

## Updating from Template

Pull updates from the upstream template:

```bash
git remote add upstream https://github.com/mcp-reg/mcp-registry-template.git
git fetch upstream
git merge upstream/main
```

## File Ownership

**You own (modify freely):**
- `registry.json`
- `config.json`
- `mcps/`
- `README.md`

**Template owns (pull updates):**
- `scripts/`
- `schemas/`
- `.github/workflows/` (validates schema on PRs)
