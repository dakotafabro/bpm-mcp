# bpm-mcp

MCP server for [BPM](https://www.usebpm.dev) - discover, inspect, and install behavioral packages from within agent sessions.

Instead of switching to a terminal to manage packages, the agent can search the registry, show you what a package does, and install it after you approve.

## Install

```bash
cd ~/development/bpm-mcp
uv pip install -e .
```

Requires the BPM CLI: `npm install -g @dakotafabrodev/agent-bpm`

## Goose Config

Add to `~/.config/goose/config.yaml`:

```yaml
bpm:
  enabled: true
  type: stdio
  name: BPM
  description: Discover and install behavioral packages
  cmd: uv
  args:
    - run
    - --directory
    - /path/to/bpm-mcp
    - bpm-mcp
  envs: {}
  env_keys: []
  timeout: 30
  bundled: false
  available_tools: []
```

## Tools

### `bpm_search(query)`

Search the BPM registry by keyword. Returns matching packages with name, type, description, version, and token cost.

### `bpm_inspect(package_name)`

Get full details about a package including its README, review status, dependencies, and peers. Use this before recommending installation.

### `bpm_install(package_name)`

Install a package. Enforces human approval before installing. Returns an approval prompt that the human must confirm before the install proceeds.

### `bpm_confirm_install(package_name, always_allow?)`

Execute the install after human approval. Set `always_allow=true` to auto-approve this package in the future.

### `bpm_remove(package_name)`

Remove an installed package.

### `bpm_list()`

List all installed packages and their total token cost.

### `bpm_set_approval_policy(mode)`

Control how installs are approved:

- `always_ask` (default) - every install requires explicit human approval
- `auto_approve_known` - packages the human has previously approved install automatically, new packages still require approval

## Approval Flow

Package installation changes agent behavior. The server enforces a two-step approval:

1. Agent calls `bpm_install("package-name")`
2. Server returns an approval prompt (not the install)
3. Human says "approve install package-name" or "always allow package-name"
4. Agent calls `bpm_confirm_install("package-name")` or `bpm_confirm_install("package-name", always_allow=true)`
5. Package installs

The approval policy is stored at `~/.bpm/mcp-policy.json`.

## How It Works

- **Search and inspect** hit the usebpm.dev registry API directly (read-only, no auth needed)
- **Install, remove, and list** shell out to the local `bpm` CLI
- The server never installs packages without going through the approval gate
- All operations are local - no data leaves your machine except registry search queries

## License

Apache 2.0
