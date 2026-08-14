from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "next_release.py"
_SPEC = importlib.util.spec_from_file_location("next_release", _SCRIPT)
assert _SPEC and _SPEC.loader
next_release = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = next_release
_SPEC.loader.exec_module(next_release)
Version = next_release.Version


def test_parse_tag_accepts_only_v_major_minor_patch() -> None:
    assert next_release.parse_tag("v0.1.0") == Version(0, 1, 0)
    assert next_release.parse_tag("v1.2.3") == Version(1, 2, 3)
    assert next_release.parse_tag("0.1.0") is None
    assert next_release.parse_tag("v1.0") is None
    assert next_release.parse_tag("v1.0.0-rc1") is None
    assert next_release.parse_tag("v01.0.0") == Version(1, 0, 0)


def test_first_release_when_repo_has_no_version_tags() -> None:
    version, tag_head = next_release.plan(frozenset(), frozenset())
    assert version == Version(0, 1, 0)
    assert tag_head is False


def test_patch_bumps_the_highest_version_tag() -> None:
    version, tag_head = next_release.plan(
        frozenset({"v0.1.0", "v0.1.2", "notes", "v2.0.0-beta"}),
        frozenset(),
    )
    assert version == Version(0, 1, 3)
    assert tag_head is False


def test_head_already_tagged_is_a_no_op_plan() -> None:
    version, tag_head = next_release.plan(
        frozenset({"v0.1.0", "v0.1.1"}),
        frozenset({"v0.1.1"}),
    )
    assert version == Version(0, 1, 1)
    assert tag_head is True


def test_cli_plan_reads_git_tags(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "ci@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "ci"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "readme").write_text("x\n")
    subprocess.run(["git", "add", "readme"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    first = subprocess.run(
        ["python3", str(_SCRIPT), "--plan"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(first.stdout) == {
        "version": "0.1.0",
        "tag": "v0.1.0",
        "tag_head": False,
    }
    subprocess.run(
        ["git", "tag", "v0.1.0"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    again = subprocess.run(
        ["python3", str(_SCRIPT), "--plan"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(again.stdout) == {
        "version": "0.1.0",
        "tag": "v0.1.0",
        "tag_head": True,
    }


def test_cli_rejects_unknown_args() -> None:
    completed = subprocess.run(
        ["python3", str(_SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2


def test_pr_workflow_has_no_release_job() -> None:
    root = Path(__file__).resolve().parents[1]
    ci = (root / ".github" / "workflows" / "ci.yml").read_text()
    release = (root / ".github" / "workflows" / "release.yml").read_text()
    assert "\n  release:" not in ci
    assert "pull_request:" not in release
    assert "next_release.py" in release
