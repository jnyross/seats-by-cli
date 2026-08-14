from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from seatspy.account import Account
from seatspy.site import HomePage, parse_routes
from seatspy.types import (
    Cabin,
    CabinDay,
    CabinStatus,
    CalendarHow,
    Csrf,
    Paths,
    Query,
    RefusalCode,
    RouteMiss,
    SearchDryRun,
    SearchHow,
    SearchRefused,
    Stage,
    YearDay,
    YearSnapshot,
    cabin_status,
    preflight_block,
)

FIXTURE = Path("/Users/johnross/Projects/SeatSpyCLI/.audit/seatspy-home.html")


def _query(**overrides: str) -> Query:
    fields = {
        "airline": "BA",
        "origin": "LHR",
        "destination": "JFK",
        "direction": "one-way",
        "cabin": "business",
        "from_date": "2026-09-01",
        "to_date": "2026-09-30",
    }
    fields.update(overrides)
    return Query.parse(**fields)


def test_routebook_ba_lhr_jfk_uses_city_ids() -> None:
    book = parse_routes(FIXTURE.read_text())
    resolved = book.resolve(_query())
    assert not isinstance(resolved, RouteMiss)
    assert resolved.origin.place_id == 657
    assert resolved.destination.place_id == 633
    assert resolved.origin.place_id not in {56, 215}
    assert resolved.destination.place_id not in {56, 215}


def test_unserved_pair_is_route_unsupported_before_post(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "cookies.txt").write_text("# Netscape HTTP Cookie File\n\n")
    book = parse_routes(FIXTURE.read_text())
    monkeypatch.setattr(
        "seatspy.account.Site.home",
        lambda self: HomePage(logged_in=True, csrf=Csrf("token"), routes=book),
    )

    def fail_post(self, csrf, route) -> None:
        raise AssertionError("submit_search should not run for an unserved pair")

    monkeypatch.setattr("seatspy.account.Site.can_search", lambda self: True)
    monkeypatch.setattr("seatspy.account.Site.submit_search", fail_post)
    outcome = Account(Paths(tmp_path)).search(_query(origin="JFK", destination="JNB"))
    assert isinstance(outcome, SearchRefused)
    assert outcome.refusal.code is RefusalCode.ROUTE_UNSUPPORTED
    assert outcome.stage is Stage.ROUTE
    assert outcome.meta.search_consumed is False


def test_cabin_status_mapping() -> None:
    assert cabin_status(4) is CabinStatus.AVAILABLE
    assert cabin_status(0) is CabinStatus.NONE
    assert cabin_status(-1) is CabinStatus.UNKNOWN
    assert cabin_status(True) is CabinStatus.UNKNOWN
    assert cabin_status("1") is CabinStatus.UNKNOWN


def test_year_snapshot_project_coverage_and_cabin_filter() -> None:
    snapshot = YearSnapshot(
        earliest=date(2026, 8, 14),
        latest=date(2027, 8, 3),
        days=(
            YearDay(date(2026, 8, 20), {Cabin.BUSINESS: CabinStatus.AVAILABLE}),
            YearDay(date(2026, 9, 2), {Cabin.BUSINESS: CabinStatus.NONE, Cabin.ECONOMY: CabinStatus.AVAILABLE}),
            YearDay(date(2026, 9, 12), {Cabin.BUSINESS: CabinStatus.AVAILABLE}),
            YearDay(date(2026, 10, 1), {Cabin.BUSINESS: CabinStatus.AVAILABLE}),
        ),
    )
    inside = snapshot.project(_query())
    assert inside.coverage == "window"
    assert [day.date for day in inside.days] == [date(2026, 9, 12)]
    assert inside.days[0].cabins == (CabinDay(Cabin.BUSINESS, CabinStatus.AVAILABLE),)

    outside = snapshot.project(_query(from_date="2026-07-01", to_date="2026-07-31"))
    assert outside.coverage == "partial"
    assert outside.days == ()


def test_dry_run_does_not_submit_search(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "cookies.txt").write_text("# Netscape HTTP Cookie File\n\n")
    book = parse_routes(FIXTURE.read_text())
    monkeypatch.setattr(
        "seatspy.account.Site.home",
        lambda self: HomePage(logged_in=True, csrf=Csrf("token"), routes=book),
    )
    monkeypatch.setattr("seatspy.account.Site.can_search", lambda self: True)

    def fail_post(self, csrf, route) -> None:
        raise AssertionError("submit_search should not run on dry-run")

    monkeypatch.setattr("seatspy.account.Site.submit_search", fail_post)
    outcome = Account(Paths(tmp_path)).search(_query(), dry_run=True)
    assert isinstance(outcome, SearchDryRun)
    assert outcome.schema == "seatspy.search.v1"
    assert outcome.exit_code == 0
    assert outcome.calendar.days == ()
    assert outcome.meta.search_consumed is False
    assert outcome.provenance.search is SearchHow.DRY_RUN
    assert outcome.provenance.calendar is CalendarHow.NONE
    payload = json.loads(outcome.to_json())
    assert payload["status"] == "ok"
    assert payload["calendar"]["days"] == []
    assert payload["meta"]["search_consumed"] is False


def test_unreadable_route_table_is_parse_failed(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "cookies.txt").write_text("# Netscape HTTP Cookie File\n\n")
    monkeypatch.setattr(
        "seatspy.account.Site.home",
        lambda self: HomePage(logged_in=True, csrf=Csrf("token"), routes=None),
    )
    monkeypatch.setattr("seatspy.account.Site.can_search", lambda self: True)
    outcome = Account(Paths(tmp_path)).search(_query())
    assert isinstance(outcome, SearchRefused)
    assert outcome.refusal.code is RefusalCode.PARSE_FAILED
    assert outcome.stage is Stage.UNKNOWN
    assert outcome.meta.search_consumed is False


def test_search_missing_jar_is_session_missing(tmp_path: Path) -> None:
    outcome = Account(Paths(tmp_path)).search(_query())
    assert isinstance(outcome, SearchRefused)
    assert outcome.refusal.code is RefusalCode.SESSION_MISSING
    assert outcome.stage is Stage.SESSION
    assert outcome.exit_code == 1


def test_preflight_block_stages() -> None:
    assert preflight_block(Stage.SESSION) == {
        "session_valid": False,
        "can_search": None,
        "route_supported": None,
    }
    assert preflight_block(Stage.SEARCHING) == {
        "session_valid": True,
        "can_search": True,
        "route_supported": True,
    }
