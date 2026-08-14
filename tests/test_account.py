from __future__ import annotations

from pathlib import Path

from seatspy.account import Account
from seatspy.site import HomePage, SignInBlocked, SignInFormRemained
from seatspy.types import (
    LoginRefused,
    Password,
    Paths,
    Query,
    QuotaOk,
    QuotaRefused,
    RefusalCode,
    SearchRefused,
)


def test_missing_jar_is_session_missing(tmp_path: Path) -> None:
    outcome = Account(Paths(tmp_path)).quota()
    assert isinstance(outcome, QuotaRefused)
    assert outcome.refusal.code is RefusalCode.SESSION_MISSING
    assert outcome.exit_code == 1


def test_quota_ok_false_is_success(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "cookies.txt").write_text("# Netscape HTTP Cookie File\n\n")
    monkeypatch.setattr("seatspy.account.Site.home", lambda self: HomePage(logged_in=True))
    monkeypatch.setattr("seatspy.account.Site.can_search", lambda self: False)
    outcome = Account(Paths(tmp_path)).quota()
    assert isinstance(outcome, QuotaOk)
    assert outcome.can_search is False
    assert outcome.exit_code == 0
    assert outcome.refused is False


def test_failed_login_keeps_working_jar(tmp_path: Path, monkeypatch) -> None:
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n# keep-me\n")
    monkeypatch.setattr(
        "seatspy.account.read_login",
        lambda token_file: ("user@example.com", Password("x")),
    )
    monkeypatch.setattr(
        "seatspy.account.Site.sign_in",
        lambda self, email, password: SignInFormRemained(),
    )
    outcome = Account(Paths(tmp_path)).login()
    assert isinstance(outcome, LoginRefused)
    assert outcome.refusal.code is RefusalCode.AUTH_FAILED
    assert cookies.read_text() == "# Netscape HTTP Cookie File\n# keep-me\n"


def test_blocked_login_is_bot_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "seatspy.account.read_login",
        lambda token_file: ("user@example.com", Password("x")),
    )
    monkeypatch.setattr(
        "seatspy.account.Site.sign_in",
        lambda self, email, password: SignInBlocked(),
    )
    outcome = Account(Paths(tmp_path)).login()
    assert isinstance(outcome, LoginRefused)
    assert outcome.refusal.code is RefusalCode.BOT_BLOCKED


def test_search_missing_jar_is_session_missing(tmp_path: Path) -> None:
    query = Query.parse(
        airline="BA",
        origin="LHR",
        destination="JFK",
        direction="one-way",
        cabin="business",
        from_date="2026-09-01",
        to_date="2026-09-30",
    )
    outcome = Account(Paths(tmp_path)).search(query)
    assert isinstance(outcome, SearchRefused)
    assert outcome.refusal.code is RefusalCode.SESSION_MISSING
    assert outcome.exit_code == 1
