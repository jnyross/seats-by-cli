from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from seatspy.cli import build_parser, main
from seatspy.types import QuotaOk, QuotaRefused, Refusal, RefusalCode


def test_argparse_has_login_and_quota() -> None:
    parser = build_parser()
    assert parser.parse_args(["login"]).command == "login"
    assert parser.parse_args(["quota"]).command == "quota"
    assert parser.parse_args(["quota", "--json"]).command == "quota"
    assert parser.parse_args(["--json", "login"]).command == "login"


def test_quota_ok_false_is_exit_0(monkeypatch, capsys) -> None:
    outcome = QuotaOk(can_search=False)
    monkeypatch.setattr(
        "seatspy.cli.Account",
        SimpleNamespace(default=lambda: SimpleNamespace(quota=lambda: outcome)),
    )
    assert main(["quota"]) == 0
    out, err = capsys.readouterr()
    payload = json.loads(out)
    assert payload["schema"] == "seatspy.quota.v1"
    assert payload["status"] == "ok"
    assert payload["can_search"] is False
    assert payload["refusal"] is None
    assert err.strip() == "No search available."


def test_missing_jar_cli_is_session_missing(monkeypatch, capsys) -> None:
    outcome = QuotaRefused(
        Refusal(RefusalCode.SESSION_MISSING, "No saved session. Run seatspy login.")
    )
    monkeypatch.setattr(
        "seatspy.cli.Account",
        SimpleNamespace(default=lambda: SimpleNamespace(quota=lambda: outcome)),
    )
    assert main(["quota"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "seatspy.quota.v1"
    assert payload["status"] == "refused"
    assert payload["refusal"]["code"] == "SESSION_MISSING"


def test_search_help() -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["search", "--help"])
    assert exc.value.code == 0


def test_search_missing_flags_exit_2() -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["search"])
    assert exc.value.code == 2


def test_search_invalid_cabin_is_exit_2(capsys) -> None:
    assert (
        main(
            [
                "search",
                "--airline",
                "BA",
                "--from",
                "LHR",
                "--to",
                "JFK",
                "--direction",
                "one-way",
                "--cabin",
                "suite",
                "--from-date",
                "2026-09-01",
                "--to-date",
                "2026-09-30",
            ]
        )
        == 2
    )
    assert capsys.readouterr().err


def test_search_parses_required_flags() -> None:
    args = build_parser().parse_args(
        [
            "search",
            "--airline",
            "BA",
            "--from",
            "LHR",
            "--to",
            "JFK",
            "--direction",
            "one-way",
            "--cabin",
            "business",
            "--from-date",
            "2026-09-01",
            "--to-date",
            "2026-09-30",
            "--dry-run",
            "--json",
        ]
    )
    assert args.command == "search"
    assert args.airline == "BA"
    assert args.origin == "LHR"
    assert args.destination == "JFK"
    assert args.direction == "one-way"
    assert args.cabin == "business"
    assert args.from_date == "2026-09-01"
    assert args.to_date == "2026-09-30"
    assert args.dry_run is True
    assert args.json is True
