from __future__ import annotations

import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_RUN = ROOT / ".cursor" / "skills" / "verify-seatspy" / "scripts" / "run.py"
_DOCTOR = ROOT / ".cursor" / "skills" / "verify-seatspy" / "scripts" / "doctor.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lock_lives_beside_cookies() -> None:
    run = _load(_RUN, "verify_run")
    assert run.LOCK.parent == run.COOKIES.parent
    assert run.LOCK == Path.home() / ".config" / "seatspy" / "live.lock"


def test_doctor_lock_matches_run() -> None:
    run = _load(_RUN, "verify_run")
    doctor = _load(_DOCTOR, "verify_doctor")
    assert doctor.LOCK == run.LOCK


def test_permission_error_keeps_lock(tmp_path: Path, monkeypatch) -> None:
    run = _load(_RUN, "verify_run")
    lock = tmp_path / "live.lock"
    lock.write_text("12345\n")
    monkeypatch.setattr(run, "LOCK", lock)

    def deny(pid: int, sig: int) -> None:
        raise PermissionError("not permitted")

    monkeypatch.setattr(os, "kill", deny)
    assert run._lock_held() is True
    assert lock.exists()


def test_missing_pid_is_stale(tmp_path: Path, monkeypatch) -> None:
    run = _load(_RUN, "verify_run")
    lock = tmp_path / "live.lock"
    lock.write_text("12345\n")
    monkeypatch.setattr(run, "LOCK", lock)

    def gone(pid: int, sig: int) -> None:
        raise ProcessLookupError("no such process")

    monkeypatch.setattr(os, "kill", gone)
    assert run._lock_held() is False
    assert not lock.exists()
