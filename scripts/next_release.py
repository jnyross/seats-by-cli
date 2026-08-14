#!/usr/bin/env python3
"""Plan the next GitHub Release from vX.Y.Z tags. Prints one JSON object."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_FIRST = (0, 1, 0)


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def tag(self) -> str:
        return f"v{self}"

    def bump_patch(self) -> Version:
        return Version(self.major, self.minor, self.patch + 1)


def parse_tag(name: str) -> Version | None:
    matched = _TAG.fullmatch(name)
    if matched is None:
        return None
    return Version(int(matched[1]), int(matched[2]), int(matched[3]))


def plan(all_tags: frozenset[str], head_tags: frozenset[str]) -> tuple[Version, bool]:
    """Return (version, tag_head). tag_head means HEAD already carries that release tag."""
    head_versions = [v for name in head_tags if (v := parse_tag(name))]
    if head_versions:
        return max(head_versions, key=lambda v: (v.major, v.minor, v.patch)), True
    versions = [v for name in all_tags if (v := parse_tag(name))]
    if not versions:
        return Version(*_FIRST), False
    return max(versions, key=lambda v: (v.major, v.minor, v.patch)).bump_patch(), False


def _tags(repo: Path, extra: list[str]) -> frozenset[str]:
    completed = subprocess.run(
        ["git", "tag", *extra],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return frozenset(line for line in completed.stdout.splitlines() if line)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args not in ([], ["--plan"]):
        print("usage: next_release.py [--plan]", file=sys.stderr)
        return 2
    repo = Path.cwd()
    version, tag_head = plan(_tags(repo, []), _tags(repo, ["--points-at", "HEAD"]))
    print(
        json.dumps(
            {"version": str(version), "tag": version.tag, "tag_head": tag_head},
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
