# bpm-mcp - what changes for you

bpm-mcp lets your agent search, inspect and install bpm packages from inside a session, without you switching to a terminal. Installs wait for your approval.

## How it equips an agent

The agent gets tools to search the registry, inspect a package (README, review status, dependencies, token cost), list what's installed, remove a package and install one. `bpm_install` doesn't install; it returns an approval prompt. Only after you say "approve install <name>" does the agent call `bpm_confirm_install`.

## When to use it

When you'd like the agent to find a package that fits a need and show you what it does first. Skip it if you'd rather every package change happen in your own terminal.

## Reserved for human judgment

Installing a package changes how your agent behaves, so approval stays with you. Read the inspect output before you approve. Two settings loosen this:

- "always allow <name>" auto-approves that package from then on.
- `auto_approve_known` auto-installs any package you approved before. The default is `always_ask`.

Removal goes through `bpm_remove`, and the README doesn't describe an approval step for it.

## What it reads, writes and sends

- Search and inspect call the usebpm.dev registry API, read-only, no auth. The README says registry search queries are the only data that leaves your machine.
- Install, remove and list run your local `bpm` CLI.
- Stores the approval policy at `~/.bpm/mcp-policy.json`.

## Cost

About 1,000 tokens of context (`token_cost` in bpm.json).

## Check it's working

Ask the agent to install a package. You should get an approval prompt, not an install.

## Turn it off

Remove the `bpm` entry from your goose config, then `bpm remove bpm-mcp`.
