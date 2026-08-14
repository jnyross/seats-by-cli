from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from seatspy.types import Password, TransportError

_LOG = logging.getLogger(__name__)
_ITEM = "seatspy.com"
_VAULT = "Product Secrets"


def read_login(token_file: Path) -> tuple[str, Password]:
    env = os.environ.copy()
    if token_file.exists():
        token = token_file.read_text().strip()
        if not token:
            raise TransportError("op service-account token file is empty")
        env["OP_SERVICE_ACCOUNT_TOKEN"] = token
        env.pop("OP_CONNECT_HOST", None)
        env.pop("OP_CONNECT_TOKEN", None)
    username = _field("username", env)
    password = Password(_field("password", env))
    _LOG.info("read login fields username_len=%s password_len=%s", len(username), len(password.reveal()))
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
