from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", f"{path} has no YAML frontmatter"
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise AssertionError(f"{path} has unterminated YAML frontmatter") from exc

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip("'\"")
    return fields


def test_all_skill_frontmatter_has_name_and_description() -> None:
    paths = sorted(
        path
        for parent in (ROOT / ".devin" / "skills", ROOT / ".cursor" / "skills")
        for path in parent.rglob("SKILL.md")
    )
    assert paths
    for path in paths:
        frontmatter = _frontmatter(path)
        assert frontmatter.get("name"), f"{path} has an empty name"
        assert frontmatter.get("description"), f"{path} has an empty description"
