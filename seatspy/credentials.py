from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from seatspy.types import Password, TransportError

_ITEM = "seatspy.com"
_VAULT = "Product Secrets"

_TOKEN_ENV_NAMES: tuple[str, ...] = (
    "OP_SERVICE_ACCOUNT_TOKEN",
    "ONEPASSWORDSA",
)

_CHILD_DROP = ("ONEPASSWORDSA", "OP_CONNECT_HOST", "OP_CONNECT_TOKEN")


@dataclass(frozen=True)
class EnvToken:
    name: str

    def describe(self) -> str:
        return f"env:{self.name}"


@dataclass(frozen=True)
class FileToken:
    path: Path
    empty: bool

    def describe(self) -> str:
        return "file"


@dataclass(frozen=True)
class NoToken:
    def describe(self) -> str:
        return "none"


TokenSource = EnvToken | FileToken | NoToken


def resolve_token_source(
    token_file: Path,
    environ: Mapping[str, str] | None = None,
) -> TokenSource:
    env = os.environ if environ is None else environ
    for name in _TOKEN_ENV_NAMES:
        if env.get(name, "").strip():
            return EnvToken(name)
    if token_file.is_file():
        return FileToken(token_file, empty=token_file.stat().st_size == 0)
    return NoToken()


def _bind_child_env(
    source: TokenSource,
    parent: Mapping[str, str],
    token_file: Path,
) -> dict[str, str]:
    child = dict(parent)
    if isinstance(source, NoToken):
        return child
    if isinstance(source, EnvToken):
        child["OP_SERVICE_ACCOUNT_TOKEN"] = parent[source.name].strip()
    else:
        text = token_file.read_text().strip()
        if not text:
            raise TransportError("op service-account token file is empty")
        child["OP_SERVICE_ACCOUNT_TOKEN"] = text
    for name in _CHILD_DROP:
        child.pop(name, None)
    return child


def read_login(
    token_file: Path,
    environ: Mapping[str, str] | None = None,
) -> tuple[str, Password]:
    parent = os.environ if environ is None else environ
    source = resolve_token_source(token_file, parent)
    try:
        child = _bind_child_env(source, parent, token_file)
        username = _field("username", child)
        password = Password(_field("password", child))
    except TransportError as exc:
        raise TransportError(f"{exc} (token source: {source.describe()})") from exc
    return username, password


def _field(name: str, env: dict[str, str]) -> str:
    argv = [
        "op",
        "item",
        "get",
        _ITEM,
        "--vault",
        _VAULT,
        "--fields",
        f"label={name}",
        "--reveal",  # op redacts the password field without this
    ]
    try:
        completed = subprocess.run(
            argv,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except FileNotFoundError as exc:
        raise TransportError("op is not installed") from exc
    except subprocess.CalledProcessError as exc:
        raise TransportError(f"could not read 1Password item {_ITEM}") from exc
    value = completed.stdout.strip()
    if not value:
        raise TransportError(f"1Password item {_ITEM} is missing {name}")
    return value
