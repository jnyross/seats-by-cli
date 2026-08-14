from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from seatspy.credentials import (
    EnvToken,
    FileToken,
    NoToken,
    read_login,
    resolve_token_source,
)
from seatspy.types import TransportError

_CREDENTIALS = Path(__file__).resolve().parents[1] / "seatspy" / "credentials.py"
_DOCTOR = (
    Path(__file__).resolve().parents[1]
    / ".cursor"
    / "skills"
    / "verify-seatspy"
    / "scripts"
    / "doctor.py"
)
_SECRET = "tok-secret-fixture-value"


def _usable(source: object) -> bool:
    return isinstance(source, EnvToken) or (
        isinstance(source, FileToken) and not source.empty
    )


def _fake_op(seen: dict[str, object]):
    def fake_run(argv, **kwargs):
        seen["env"] = kwargs["env"]
        seen["called"] = True
        field = argv[argv.index("--fields") + 1]
        value = "user@example.com" if field.endswith("username") else "pw-secret"
        return SimpleNamespace(stdout=value + "\n")

    return fake_run


def test_token_stays_in_child_env(tmp_path: Path, monkeypatch) -> None:
    token_file = tmp_path / "op-service-account-token"
    token_file.write_text("tok-secret\n")
    seen: dict[str, object] = {}

    monkeypatch.setattr(subprocess, "run", _fake_op(seen))
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.delenv("ONEPASSWORDSA", raising=False)
    username, password = read_login(token_file)
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["OP_SERVICE_ACCOUNT_TOKEN"] == "tok-secret"
    assert "OP_SERVICE_ACCOUNT_TOKEN" not in os.environ
    assert username == "user@example.com"
    assert password.reveal() == "pw-secret"
    assert "pw-secret" not in repr(password)


def test_read_login_does_not_log_secret_lengths() -> None:
    source = _CREDENTIALS.read_text()
    assert "password_len" not in source
    assert "username_len" not in source


def test_missing_op_is_transport_error(tmp_path: Path, monkeypatch) -> None:
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("op")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(TransportError, match="op is not installed"):
        read_login(tmp_path / "missing-token", environ={})


def test_alias_env_reaches_child_only(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(subprocess, "run", _fake_op(seen))
    parent = {"ONEPASSWORDSA": _SECRET}
    read_login(tmp_path / "missing-token", environ=parent)
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["OP_SERVICE_ACCOUNT_TOKEN"] == _SECRET
    assert "ONEPASSWORDSA" not in env
    assert "OP_SERVICE_ACCOUNT_TOKEN" not in parent
    assert "OP_SERVICE_ACCOUNT_TOKEN" not in os.environ


def test_standard_env_wins_over_alias(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(subprocess, "run", _fake_op(seen))
    parent = {
        "OP_SERVICE_ACCOUNT_TOKEN": "standard-secret",
        "ONEPASSWORDSA": "alias-secret",
        "OP_CONNECT_HOST": "https://connect.example",
        "OP_CONNECT_TOKEN": "connect-secret",
    }
    read_login(tmp_path / "missing-token", environ=parent)
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["OP_SERVICE_ACCOUNT_TOKEN"] == "standard-secret"
    assert "ONEPASSWORDSA" not in env
    assert "OP_CONNECT_HOST" not in env
    assert "OP_CONNECT_TOKEN" not in env
    assert parent["ONEPASSWORDSA"] == "alias-secret"


def test_env_wins_over_file(tmp_path: Path, monkeypatch) -> None:
    token_file = tmp_path / "op-service-account-token"
    token_file.write_text("file-secret\n")
    seen: dict[str, object] = {}
    monkeypatch.setattr(subprocess, "run", _fake_op(seen))
    read_login(token_file, environ={"OP_SERVICE_ACCOUNT_TOKEN": "env-secret"})
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["OP_SERVICE_ACCOUNT_TOKEN"] == "env-secret"


def test_empty_alias_falls_through_to_file(tmp_path: Path, monkeypatch) -> None:
    token_file = tmp_path / "op-service-account-token"
    token_file.write_text("file-secret\n")
    seen: dict[str, object] = {}
    monkeypatch.setattr(subprocess, "run", _fake_op(seen))
    read_login(token_file, environ={"ONEPASSWORDSA": "  "})
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["OP_SERVICE_ACCOUNT_TOKEN"] == "file-secret"


def test_empty_file_is_transport_error(tmp_path: Path, monkeypatch) -> None:
    token_file = tmp_path / "op-service-account-token"
    token_file.write_text("")

    def fail_run(argv, **kwargs):
        raise AssertionError("op should not run for an empty token file")

    monkeypatch.setattr(subprocess, "run", fail_run)
    with pytest.raises(TransportError, match="empty") as caught:
        read_login(token_file, environ={})
    assert "token source: file" in str(caught.value)
    assert _SECRET not in str(caught.value)


def test_no_token_still_invokes_op(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(subprocess, "run", _fake_op(seen))
    read_login(tmp_path / "missing-token", environ={})
    assert seen.get("called") is True
    env = seen["env"]
    assert isinstance(env, dict)
    assert "OP_SERVICE_ACCOUNT_TOKEN" not in env


def test_resolve_token_source_variants(tmp_path: Path) -> None:
    env_source = resolve_token_source(
        tmp_path / "missing-token",
        {"OP_SERVICE_ACCOUNT_TOKEN": _SECRET},
    )
    assert env_source == EnvToken(name="OP_SERVICE_ACCOUNT_TOKEN")
    assert env_source.describe() == "env:OP_SERVICE_ACCOUNT_TOKEN"
    assert _SECRET not in repr(env_source)

    alias_source = resolve_token_source(
        tmp_path / "missing-token",
        {"ONEPASSWORDSA": _SECRET},
    )
    assert alias_source == EnvToken(name="ONEPASSWORDSA")
    assert alias_source.describe() == "env:ONEPASSWORDSA"
    assert _SECRET not in repr(alias_source)

    token_file = tmp_path / "op-service-account-token"
    token_file.write_text(_SECRET)
    file_source = resolve_token_source(token_file, {})
    assert file_source == FileToken(path=token_file, empty=False)
    assert file_source.describe() == "file"
    assert _SECRET not in repr(file_source)

    empty_file = tmp_path / "empty-token"
    empty_file.write_text("")
    empty_source = resolve_token_source(empty_file, {})
    assert empty_source == FileToken(path=empty_file, empty=True)
    assert empty_source.describe() == "file"

    none_source = resolve_token_source(tmp_path / "missing-token", {})
    assert none_source == NoToken()
    assert none_source.describe() == "none"


def test_empty_and_none_sources_are_not_usable(tmp_path: Path) -> None:
    assert _usable(NoToken()) is False
    assert _usable(FileToken(tmp_path / "empty-token", empty=True)) is False
    assert _usable(EnvToken("OP_SERVICE_ACCOUNT_TOKEN")) is True
    assert _usable(FileToken(tmp_path / "token", empty=False)) is True


def test_error_names_source_kind_not_value(tmp_path: Path, monkeypatch) -> None:
    def fake_run(argv, **kwargs):
        raise subprocess.CalledProcessError(1, argv)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(TransportError) as caught:
        read_login(
            tmp_path / "missing-token",
            environ={"ONEPASSWORDSA": _SECRET},
        )
    message = str(caught.value)
    assert "token source: env:ONEPASSWORDSA" in message
    assert _SECRET not in message


def test_doctor_does_not_read_token_bytes() -> None:
    source = _DOCTOR.read_text()
    assert "TOKEN.read_text" not in source
    assert "resolve_token_source" in source
    assert "token_source" in source
    assert "token_file_exist" in source
    assert "token_exist" in source
