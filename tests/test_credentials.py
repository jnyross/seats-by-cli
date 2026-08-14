from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from seatspy.credentials import read_login
from seatspy.types import TransportError


def test_token_stays_in_child_env(tmp_path: Path, monkeypatch) -> None:
    token_file = tmp_path / "op-service-account-token"
    token_file.write_text("tok-secret\n")
    seen: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        seen["env"] = kwargs["env"]
        field = argv[argv.index("--fields") + 1]
        value = "user@example.com" if field.endswith("username") else "pw-secret"
        return SimpleNamespace(stdout=value + "\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    os.environ.pop("OP_SERVICE_ACCOUNT_TOKEN", None)
    username, password = read_login(token_file)
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["OP_SERVICE_ACCOUNT_TOKEN"] == "tok-secret"
    assert "OP_SERVICE_ACCOUNT_TOKEN" not in os.environ
    assert username == "user@example.com"
    assert password.reveal() == "pw-secret"
    assert "pw-secret" not in repr(password)


def test_missing_op_is_transport_error(tmp_path: Path, monkeypatch) -> None:
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("op")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(TransportError, match="op is not installed"):
        read_login(tmp_path / "missing-token")
