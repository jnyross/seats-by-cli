from __future__ import annotations

import http.cookiejar
import os
from pathlib import Path


class SessionStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def replacement(self, jar: http.cookiejar.MozillaCookieJar) -> None:
        dest = self._path
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(dest.parent, 0o700)
        tmp = dest.with_name(dest.name + ".tmp")
        if tmp.exists():
            tmp.unlink()
        out = http.cookiejar.MozillaCookieJar(str(tmp))
        for cookie in jar:
            out.set_cookie(cookie)
        # Session cookies are marked discard. Drop them and the next request is anonymous.
        out.save(ignore_discard=True, ignore_expires=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, dest)
        os.chmod(dest, 0o600)
