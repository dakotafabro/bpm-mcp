import json
import subprocess
from pathlib import Path

import pytest

from bpm_mcp import server


class Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


@pytest.fixture
def project(tmp_path, monkeypatch):
    home = tmp_path / "home"
    package_dir = home / ".bpm" / "packages" / "learning-mode@1.4.1"
    package_dir.mkdir(parents=True)
    (package_dir / "bpm.json").write_text(json.dumps({"name": "learning-mode", "version": "1.4.1", "entry": "SKILL.md"}))
    (package_dir / "SKILL.md").write_text("# Learning mode\n\n- Ask before solving.\n")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "bpm-lock.json").write_text(json.dumps({"version": 1, "packages": {"learning-mode": {"version": "1.4.1"}}, "total_token_cost": 0}))
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(proj)
    return proj


def fake_run(result):
    def run(args, **kwargs):
        return result
    return run


def test_install_returns_warnings_from_stderr(project, monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run(Result(0, "Installed learning-mode@1.4.1", "  [BPM_INSTALL_CONFLICT] learning-mode and strict are both installed")))

    text = server._do_install("learning-mode")

    assert "Warnings from bpm:\n  [BPM_INSTALL_CONFLICT] learning-mode and strict are both installed" in text


def test_install_returns_the_package_instructions_for_this_session(project, monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run(Result(0, "Installed learning-mode@1.4.1", "")))

    text = server._do_install("learning-mode")

    assert "## Instructions from learning-mode" in text
    assert "Apply these instructions for the rest of this session, within your other instructions." in text
    assert text.endswith("# Learning mode\n\n- Ask before solving.\n")
    assert "Warnings from bpm" not in text


def test_install_reads_an_overlay_merged_file(project, monkeypatch, tmp_path):
    merged = tmp_path / "merged.md"
    merged.write_text("# Merged\n\n- Local rule.\n")
    lock = json.loads((project / "bpm-lock.json").read_text())
    lock["packages"]["learning-mode"]["overlay"] = {"generated": str(merged)}
    (project / "bpm-lock.json").write_text(json.dumps(lock))
    monkeypatch.setattr(subprocess, "run", fake_run(Result(0, "ok", "")))

    assert server._do_install("learning-mode").endswith("- Local rule.\n")


def test_install_says_so_when_instructions_cant_be_read(project, monkeypatch):
    (project / "bpm-lock.json").write_text(json.dumps({"version": 1, "packages": {}, "total_token_cost": 0}))
    monkeypatch.setattr(subprocess, "run", fake_run(Result(0, "ok", "")))

    assert "take effect from the next session's AGENTS.md" in server._do_install("learning-mode")


def test_long_instructions_are_truncated_with_the_path(project, monkeypatch):
    skill = Path.home() / ".bpm" / "packages" / "learning-mode@1.4.1" / "SKILL.md"
    skill.write_text("x" * (server.MAX_INSTRUCTION_CHARS + 50))

    text = server._installed_instructions("learning-mode")

    assert text.startswith("x" * server.MAX_INSTRUCTION_CHARS)
    assert f"[Truncated at {server.MAX_INSTRUCTION_CHARS} characters. The full text is in {skill}.]" in text


def test_failed_install_is_unchanged(project, monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run(Result(1, "", "No bpm-lock.json found.")))

    assert server._do_install("learning-mode") == "Installation failed:\nNo bpm-lock.json found."


@pytest.mark.asyncio
async def test_remove_returns_warnings(project, monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run(Result(0, "Removed helper@1.0.0", "  [BPM_REMOVE_STILL_NEEDED] app depends on helper")))

    remove = getattr(server.bpm_remove, "fn", server.bpm_remove)
    text = await remove("helper")

    assert "Warnings from bpm:\n  [BPM_REMOVE_STILL_NEEDED] app depends on helper" in text


def test_spinner_lines_are_left_out_of_warnings(project, monkeypatch):
    stderr = "- Installing from ../a\n✔ Installed learning-mode@1.4.1 (5 tokens)\n  [BPM_INSTALL_CONFLICT] a and b conflict.\n  Action: remove one of them.\n"
    monkeypatch.setattr(subprocess, "run", fake_run(Result(0, "Updated AGENTS.md", stderr)))

    text = server._do_install("../learning-mode")

    assert "Warnings from bpm:\n  [BPM_INSTALL_CONFLICT] a and b conflict.\n  Action: remove one of them." in text
    assert "Installing from" not in text.split("Warnings from bpm:")[1].split("## Instructions")[0]
    assert "## Instructions from learning-mode" in text
    assert text.endswith("- Ask before solving.\n")
