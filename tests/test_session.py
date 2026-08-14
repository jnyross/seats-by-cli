from __future__ import annotations

import stat
from http.cookiejar import Cookie, MozillaCookieJar
from pathlib import Path

from seatspy.session import SessionStore


def _cookie() -> Cookie:
    return Cookie(
        version=0,
        name="session",
        value="abc",
        port=None,
        port_specified=False,
        domain=".seatspy.com",
        domain_specified=True,
        domain_initial_dot=True,
        path="/",
        path_specified=True,
        secure=True,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={"HttpOnly": None},
        rfc2109=False,
    )


def test_replacement_writes_atomically(tmp_path: Path) -> None:
    dest = tmp_path / "cookies.txt"
    dest.write_text("stale-jar\n")
    jar = MozillaCookieJar()
    jar.set_cookie(_cookie())
    SessionStore(dest).replacement(jar)
    assert dest.exists()
    assert not dest.with_name("cookies.txt.tmp").exists()
    assert "stale-jar" not in dest.read_text()
    assert "session" in dest.read_text()
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700


def test_replacement_creates_directory(tmp_path: Path) -> None:
    dest = tmp_path / "seatspy" / "cookies.txt"
    jar = MozillaCookieJar()
    jar.set_cookie(_cookie())
    SessionStore(dest).replacement(jar)
    assert dest.exists()
    assert stat.S_IMODE(dest.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
