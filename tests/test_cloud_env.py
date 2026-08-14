from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cloud-env.sh"


def _wire(tmp_path: Path, **tokens: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("OP_SERVICE_ACCOUNT_TOKEN", None)
    env.pop("ONEPASSWORDSA", None)
    env.update(tokens)
    env["HOME"] = str(tmp_path)
    return subprocess.run(
        ["bash", str(SCRIPT), "wire"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_wire_accepts_cursor_secret_alias_without_printing_it(tmp_path: Path) -> None:
    result = _wire(tmp_path, ONEPASSWORDSA="alias-value")
    token_file = tmp_path / ".config" / "seatspy" / "op-service-account-token"

    assert token_file.read_text() == "alias-value\n"
    assert "alias-value" not in result.stdout
    assert "alias-value" not in result.stderr


def test_wire_prefers_standard_secret_name(tmp_path: Path) -> None:
    _wire(
        tmp_path,
        OP_SERVICE_ACCOUNT_TOKEN="standard-value",
        ONEPASSWORDSA="alias-value",
    )
    token_file = tmp_path / ".config" / "seatspy" / "op-service-account-token"

    assert token_file.read_text() == "standard-value\n"
