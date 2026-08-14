#!/usr/bin/env python3
"""Read-only check that this checkout is worth driving."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
VENV = ROOT / ".venv" / "bin" / "python"
PYTHON = VENV if VENV.exists() else Path(sys.executable)
CONFIG = Path.home() / ".config" / "seatspy"
COOKIES = CONFIG / "cookies.txt"
TOKEN = CONFIG / "op-service-account-token"
LOCK = CONFIG / "live.lock"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)


def main() -> int:
    report: dict[str, object] = {
        "root": str(ROOT),
        "python": str(PYTHON),
        "import_ok": False,
        "help": {},
        "cookies_exist": COOKIES.exists(),
        "token_exist": TOKEN.exists(),
        "live_lock": None,
        "ok": False,
    }
    try:
        import seatspy  # noqa: F401
    except ImportError as exc:
        report["import_error"] = str(exc)
        print(json.dumps(report, indent=2))
        return 1
    report["import_ok"] = True

    help_ok = True
    for command in ("login", "quota", "search"):
        completed = _run([str(PYTHON), "-m", "seatspy", command, "--help"])
        report["help"][command] = completed.returncode
        if completed.returncode != 0:
            help_ok = False

    if LOCK.exists():
        raw = LOCK.read_text().strip()
        try:
            pid = int(raw)
        except ValueError:
            report["live_lock"] = {"pid": None, "alive": True}
            print(json.dumps(report, indent=2))
            return 1
        alive = _pid_alive(pid)
        report["live_lock"] = {"pid": pid, "alive": alive}
        if alive:
            print(json.dumps(report, indent=2))
            return 1

    report["ok"] = help_ok
    print(json.dumps(report, indent=2))
    return 0 if help_ok else 1


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


if __name__ == "__main__":
    sys.exit(main())
