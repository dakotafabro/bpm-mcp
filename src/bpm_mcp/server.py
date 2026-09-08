from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx
from fastmcp import FastMCP

REGISTRY_URL = "https://www.usebpm.dev"
APPROVAL_POLICY_PATH = Path.home() / ".bpm" / "mcp-policy.json"

INSTRUCTIONS = """BPM MCP Server - discover, inspect, and install behavioral packages for AI agents.

Use bpm_search to find packages by keyword. Use bpm_inspect to read full details
and README before recommending installation. Use bpm_install to install a package
after the human approves. Use bpm_list to see what's currently installed.
Use bpm_remove to uninstall a package.

IMPORTANT: Package installation changes agent behavior. Always present the package
details to the human and get explicit approval before calling bpm_install.
The install tool will enforce this - it returns approval instructions rather than
installing silently.
"""

mcp = FastMCP(
    "BPM",
    instructions=INSTRUCTIONS,
)


def _load_approval_policy() -> dict:
    if APPROVAL_POLICY_PATH.exists():
        try:
            return json.loads(APPROVAL_POLICY_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"mode": "always_ask", "auto_approved": []}


def _save_approval_policy(policy: dict) -> None:
    APPROVAL_POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVAL_POLICY_PATH.write_text(json.dumps(policy, indent=2))


@mcp.tool()
async def bpm_search(query: str) -> str:
    """Search the BPM registry for behavioral packages.

    Args:
        query: Search terms (e.g. "accessibility review", "learning", "security")

    Returns:
        Matching packages with name, type, description, version, and token cost.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{REGISTRY_URL}/api/packages",
            params={"search": query},
        )
        resp.raise_for_status()
        data = resp.json()

    packages = data.get("packages", [])
    if not packages:
        return f"No packages found for '{query}'."

    lines = [f"Found {len(packages)} package(s) for '{query}':\n"]
    for pkg in packages:
        name = pkg.get("name", "unknown")
        pkg_type = pkg.get("type", "unknown")
        desc = pkg.get("description", "")
        version = pkg.get("latest_version", "?")
        bpm_json = {}
        versions = pkg.get("versions", [])
        if versions:
            bpm_json = versions[0].get("bpm_json", {})
        token_cost = bpm_json.get("token_cost", "?")
        keywords = ", ".join(pkg.get("keywords", []))

        lines.append(f"**{name}** v{version} ({pkg_type})")
        lines.append(f"  {desc}")
        lines.append(f"  Token cost: {token_cost} | Keywords: {keywords}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def bpm_inspect(package_name: str) -> str:
    """Get full details about a BPM package including its README.

    Use this before recommending installation so the human can review
    what the package does and how it changes agent behavior.

    Args:
        package_name: The package name (e.g. "learning-mode", "mastery")

    Returns:
        Full package metadata, README content, and review status.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{REGISTRY_URL}/api/packages/{package_name}")
        if resp.status_code == 404:
            return f"Package '{package_name}' not found in the registry."
        resp.raise_for_status()
        pkg = resp.json()

    name = pkg.get("name", "unknown")
    desc = pkg.get("description", "")
    pkg_type = pkg.get("type", "unknown")
    version = pkg.get("latest_version", "?")
    readme = pkg.get("readme", "No README available.")
    repo = pkg.get("repository", "")
    license_val = ""
    agents = ", ".join(pkg.get("agents", []))
    review_status = pkg.get("last_review_status", "unknown")
    author = pkg.get("author", {})
    author_name = author.get("name", "unknown")

    bpm_json = {}
    versions = pkg.get("versions", [])
    if versions:
        bpm_json = versions[0].get("bpm_json", {})
    token_cost = bpm_json.get("token_cost", "?")
    scope = bpm_json.get("scope", "?")
    license_val = bpm_json.get("license", "?")
    keywords = ", ".join(bpm_json.get("keywords", []))
    peers = ", ".join(bpm_json.get("peers", [])) or "none"
    deps = ", ".join(bpm_json.get("dependencies", [])) or "none"

    lines = [
        f"# {name} v{version}",
        "",
        f"**Type:** {pkg_type}",
        f"**Scope:** {scope}",
        f"**Token cost:** {token_cost}",
        f"**License:** {license_val}",
        f"**Author:** {author_name}",
        f"**Repository:** {repo}",
        f"**Agents:** {agents}",
        f"**Review status:** {review_status}",
        f"**Keywords:** {keywords}",
        f"**Dependencies:** {deps}",
        f"**Peers:** {peers}",
        "",
        "---",
        "",
        desc,
        "",
        "---",
        "",
        readme,
    ]

    return "\n".join(lines)


@mcp.tool()
async def bpm_install(package_name: str) -> str:
    """Install a BPM package into the current project.

    This changes agent behavior. The tool enforces human approval before
    installing. If the package is not pre-approved, it returns instructions
    for the human to confirm.

    Args:
        package_name: The package to install (e.g. "learning-mode")

    Returns:
        Installation result or approval prompt.
    """
    policy = _load_approval_policy()
    mode = policy.get("mode", "always_ask")
    auto_approved = policy.get("auto_approved", [])

    if mode == "always_ask" or (
        mode == "auto_approve_known" and package_name not in auto_approved
    ):
        return (
            f"**Approval required.**\n\n"
            f"Installing `{package_name}` will change agent behavior for this project.\n\n"
            f"Please confirm one of the following:\n"
            f"- \"approve install {package_name}\" - install this once\n"
            f"- \"always allow {package_name}\" - auto-approve this package in the future\n"
            f"- \"deny\" - do not install\n\n"
            f"To change the approval policy globally, use `bpm_set_approval_policy`."
        )

    return _do_install(package_name)


@mcp.tool()
async def bpm_confirm_install(package_name: str, always_allow: bool = False) -> str:
    """Confirm installation of a BPM package after human approval.

    Only call this after the human has explicitly approved the install.

    Args:
        package_name: The package to install
        always_allow: If true, add this package to the auto-approved list
    """
    if always_allow:
        policy = _load_approval_policy()
        if package_name not in policy.get("auto_approved", []):
            policy.setdefault("auto_approved", []).append(package_name)
            _save_approval_policy(policy)

    return _do_install(package_name)


def _do_install(package_name: str) -> str:
    try:
        result = subprocess.run(
            ["bpm", "install", package_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            error = result.stderr.strip() or output
            return f"Installation failed:\n{error}"
        return f"Installed `{package_name}`.\n\n{output}"
    except FileNotFoundError:
        return "Error: `bpm` CLI not found. Install it with: npm install -g @dakotafabrodev/agent-bpm"
    except subprocess.TimeoutExpired:
        return "Error: Installation timed out after 30 seconds."


@mcp.tool()
async def bpm_remove(package_name: str) -> str:
    """Remove an installed BPM package.

    Args:
        package_name: The package to remove
    """
    try:
        result = subprocess.run(
            ["bpm", "remove", package_name],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            error = result.stderr.strip() or output
            return f"Removal failed:\n{error}"
        return f"Removed `{package_name}`.\n\n{output}"
    except FileNotFoundError:
        return "Error: `bpm` CLI not found."
    except subprocess.TimeoutExpired:
        return "Error: Removal timed out."


@mcp.tool()
async def bpm_list() -> str:
    """List all installed BPM packages and their total token cost."""
    try:
        result = subprocess.run(
            ["bpm", "list"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            error = result.stderr.strip() or output
            return f"Failed to list packages:\n{error}"
        if not output:
            return "No packages installed. Use `bpm_search` to find packages."
        return output
    except FileNotFoundError:
        return "Error: `bpm` CLI not found. Install it with: npm install -g @dakotafabrodev/agent-bpm"
    except subprocess.TimeoutExpired:
        return "Error: List command timed out."


@mcp.tool()
async def bpm_set_approval_policy(mode: str) -> str:
    """Set the install approval policy for BPM packages.

    Args:
        mode: One of:
            - "always_ask" (default) - require human approval for every install
            - "auto_approve_known" - auto-approve packages the human has previously approved,
              ask for new ones
    """
    valid_modes = ["always_ask", "auto_approve_known"]
    if mode not in valid_modes:
        return f"Invalid mode. Choose one of: {', '.join(valid_modes)}"

    policy = _load_approval_policy()
    policy["mode"] = mode
    _save_approval_policy(policy)

    if mode == "always_ask":
        return "Approval policy set to **always ask**. Every install requires explicit human approval."
    else:
        approved = policy.get("auto_approved", [])
        if approved:
            return (
                f"Approval policy set to **auto-approve known**.\n"
                f"Pre-approved packages: {', '.join(approved)}\n"
                f"New packages will still require approval."
            )
        return (
            "Approval policy set to **auto-approve known**.\n"
            "No packages pre-approved yet. First install of each package will require approval."
        )


def main() -> None:
    mcp.run()
