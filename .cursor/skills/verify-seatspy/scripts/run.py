#!/usr/bin/env python3
"""Run one seatspy CLI command and write proof artifacts. Never copies cookies."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
VENV = ROOT / ".venv" / "bin" / "python"
PYTHON = VENV if VENV.exists() else Path(sys.executable)
RUNS = ROOT / ".verify" / "runs"
CONFIG = Path.home() / ".config" / "seatspy"
COOKIES = CONFIG / "cookies.txt"
LOCK = CONFIG / "live.lock"


def main() -> int:
    parser = argparse.ArgumentParser(description="Drive seatspy and capture evidence.")
    parser.add_argument("--feature", required=True, help="Feature id from the map, such as quota-json.")
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="seatspy argv after -- . Example: -- quota --json",
    )
    args = parser.parse_args()
    argv = list(args.command)
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print("usage: run.py --feature <id> -- <seatspy-args>", file=sys.stderr)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = RUNS / f"{stamp}-{args.feature}"
    dest.mkdir(parents=True, exist_ok=True)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if _lock_held() or not _acquire():
        (dest / "summary.json").write_text(
            json.dumps({"ok": False, "error": "live lock held; refuse second drive"}, indent=2)
        )
        print(dest)
        return 2
    cookies_before = COOKIES.exists()
    try:
        completed = subprocess.run(
            [str(PYTHON), "-m", "seatspy", *argv],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
    finally:
        if LOCK.exists() and LOCK.read_text().strip() == str(os.getpid()):
            LOCK.unlink()

    (dest / "command.txt").write_text(" ".join(["python", "-m", "seatspy", *argv]) + "\n")
    (dest / "stdout.txt").write_text(completed.stdout)
    (dest / "stderr.txt").write_text(completed.stderr)
    (dest / "exit.txt").write_text(str(completed.returncode) + "\n")
    payload = _parse_json(completed.stdout)
    if payload is not None:
        (dest / "stdout.json").write_text(json.dumps(payload, indent=2) + "\n")
    summary = _summarize(
        feature=args.feature,
        argv=argv,
        exit_code=completed.returncode,
        stderr=completed.stderr.strip(),
        payload=payload,
        cookies_before=cookies_before,
        cookies_after=COOKIES.exists(),
    )
    (dest / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(dest)
    return 0 if summary.get("ok") else 1


def _lock_held() -> bool:
    if not LOCK.exists():
        return False
    raw = LOCK.read_text().strip()
    try:
        pid = int(raw)
    except ValueError:
        return True
    if pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        LOCK.unlink()
        return False
    except OSError:
        return True
    return True


def _acquire() -> bool:
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    try:
        os.write(fd, f"{os.getpid()}\n".encode())
    finally:
        os.close(fd)
    return True


def _parse_json(raw: str) -> dict[str, object] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _summarize(
    *,
    feature: str,
    argv: list[str],
    exit_code: int,
    stderr: str,
    payload: dict[str, object] | None,
    cookies_before: bool,
    cookies_after: bool,
) -> dict[str, object]:
    calendar = payload.get("calendar") if payload else None
    days = calendar.get("days") if isinstance(calendar, dict) else None
    refusal = payload.get("refusal") if payload else None
    summary: dict[str, object] = {
        "feature": feature,
        "argv": argv,
        "exit_code": exit_code,
        "stderr": stderr,
        "schema": None if payload is None else payload.get("schema"),
        "status": None if payload is None else payload.get("status"),
        "refusal_code": refusal.get("code") if isinstance(refusal, dict) else None,
        "can_search": None if payload is None else payload.get("can_search"),
        "stored": None if payload is None else payload.get("stored"),
        "search_consumed": (payload.get("meta") or {}).get("search_consumed")
        if isinstance(payload, dict) and isinstance(payload.get("meta"), dict)
        else None,
        "day_count": len(days) if isinstance(days, list) else None,
        "coverage": calendar.get("coverage") if isinstance(calendar, dict) else None,
        "cookies_existed_before": cookies_before,
        "cookies_exist_after": cookies_after,
        "ok": False,
    }
    if payload is None:
        return summary
    summary["ok"] = True
    return summary


if __name__ == "__main__":
    sys.exit(main())
