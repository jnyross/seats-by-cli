from __future__ import annotations

import ast
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

import pytest

from seatspy.account import Account
from seatspy.cli import build_parser, main
from seatspy.site import HomePage, SearchPosted
from seatspy.snapshots import SnapshotError, SnapshotStore
from seatspy.types import (
    Appeared,
    Cabin,
    CabinDay,
    CabinStatus,
    Calendar,
    CalendarChanged,
    CalendarHow,
    CalendarUnchanged,
    Csrf,
    Day,
    DiffChanged,
    DiffNoPrevious,
    DiffUnchanged,
    Meta,
    Paths,
    Provenance,
    Query,
    SearchDryRun,
    SearchHow,
    SearchOk,
    SearchRefused,
    StatusChanged,
    Vanished,
    YearDay,
    YearSnapshot,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "seatspy-home.html"
DOCTOR = Path(__file__).resolve().parents[1] / ".cursor" / "skills" / "verify-seatspy" / "scripts" / "doctor.py"
SEP12 = date(2026, 9, 12)
SEP13 = date(2026, 9, 13)
SEP14 = date(2026, 9, 14)
FIRST = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)
SECOND = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
THIRD = datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc)
DIFF_ARGV = [
    "diff",
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
    "--json",
]


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


def _calendar(
    *pairs: tuple[date, CabinStatus], coverage: Literal["window", "partial"] = "window"
) -> Calendar:
    days = tuple(Day(day, (CabinDay(Cabin.BUSINESS, status),)) for day, status in pairs)
    return Calendar(coverage, days)


def _ok(calendar: Calendar, fetched_at: datetime, query: Query | None = None) -> SearchOk:
    return SearchOk(
        query=query or _query(),
        provenance=Provenance(SearchHow.HTTP_FORM_POST, CalendarHow.HTTP_PARSE),
        calendar=calendar,
        meta=Meta(fetched_at, "https://www.seatspy.com", True),
    )


def _store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(Paths(tmp_path))


def _payload(capsys) -> dict[str, object]:
    out, _err = capsys.readouterr()
    return json.loads(out)


def test_zero_snapshots_is_no_previous(tmp_path: Path) -> None:
    outcome = _store(tmp_path).diff(_query())
    assert isinstance(outcome, DiffNoPrevious)
    assert outcome.current is None
    assert outcome.exit_code == 0
    payload = json.loads(outcome.to_json())
    assert payload["status"] == "ok"
    assert payload["comparison"] == "no_previous_snapshot"
    assert payload["stored"] == 0
    assert payload["snapshots"] == {"previous": None, "current": None}
    assert payload["changes"] == []
    assert payload["meta"] == {"search_consumed": False, "source": "local_snapshots"}
    assert payload["refusal"] is None
    assert outcome.message == "No snapshot for this query. Run seatspy search twice."


def test_one_snapshot_is_no_previous(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record(_ok(_calendar((SEP12, CabinStatus.AVAILABLE)), FIRST))
    outcome = store.diff(_query())
    assert isinstance(outcome, DiffNoPrevious)
    assert outcome.current is not None
    assert outcome.exit_code == 0
    payload = json.loads(outcome.to_json())
    assert payload["comparison"] == "no_previous_snapshot"
    assert payload["stored"] == 1
    assert payload["snapshots"]["previous"] is None
    assert payload["snapshots"]["current"]["coverage"] == "window"
    assert payload["changes"] == []
    assert outcome.message == "No previous snapshot for this query. Run seatspy search once more."


def test_appeared_day(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record(_ok(_calendar(), FIRST))
    store.record(_ok(_calendar((SEP12, CabinStatus.AVAILABLE)), SECOND))
    outcome = store.diff(_query())
    assert isinstance(outcome, DiffChanged)
    assert outcome.changes.to_tuple() == (Appeared(SEP12, CabinStatus.AVAILABLE),)
    payload = json.loads(outcome.to_json())
    assert payload["comparison"] == "changed"
    assert payload["changes"] == [
        {"date": "2026-09-12", "change": "appeared", "before": "none", "after": "available"}
    ]


def test_vanished_day_after_project_drops_none(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record(_ok(_calendar((SEP13, CabinStatus.AVAILABLE)), FIRST))
    store.record(_ok(_calendar(), SECOND))
    outcome = store.diff(_query())
    assert isinstance(outcome, DiffChanged)
    assert outcome.changes.to_tuple() == (Vanished(SEP13, CabinStatus.AVAILABLE),)
    payload = json.loads(outcome.to_json())
    assert payload["changes"] == [
        {"date": "2026-09-13", "change": "vanished", "before": "available", "after": "none"}
    ]


def test_status_changed_available_to_waitlist(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record(_ok(_calendar((SEP14, CabinStatus.AVAILABLE)), FIRST))
    store.record(_ok(_calendar((SEP14, CabinStatus.WAITLIST)), SECOND))
    outcome = store.diff(_query())
    assert isinstance(outcome, DiffChanged)
    assert outcome.changes.to_tuple() == (
        StatusChanged(SEP14, CabinStatus.AVAILABLE, CabinStatus.WAITLIST),
    )
    payload = json.loads(outcome.to_json())
    assert payload["changes"] == [
        {
            "date": "2026-09-14",
            "change": "status_changed",
            "before": "available",
            "after": "waitlist",
        }
    ]


def test_identical_calendars_are_unchanged(tmp_path: Path) -> None:
    store = _store(tmp_path)
    calendar = _calendar((SEP12, CabinStatus.AVAILABLE))
    store.record(_ok(calendar, FIRST))
    store.record(_ok(calendar, SECOND))
    outcome = store.diff(_query())
    assert isinstance(outcome, DiffUnchanged)
    assert outcome.exit_code == 0
    payload = json.loads(outcome.to_json())
    assert payload["comparison"] == "unchanged"
    assert payload["changes"] == []
    assert payload["stored"] == 2
    assert outcome.message == "No changes since the previous snapshot."


def test_query_mismatch_is_first_run_for_the_other_ask(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record(_ok(_calendar((SEP12, CabinStatus.AVAILABLE)), FIRST))
    store.record(_ok(_calendar((SEP12, CabinStatus.WAITLIST)), SECOND))
    other = _query(destination="LAX")
    outcome = store.diff(other)
    assert isinstance(outcome, DiffNoPrevious)
    payload = json.loads(outcome.to_json())
    assert payload["comparison"] == "no_previous_snapshot"
    assert payload["stored"] == 0
    assert payload["query"]["destination"] == "LAX"


def test_dry_run_and_refused_search_do_not_persist(tmp_path: Path, monkeypatch) -> None:
    from seatspy.site import parse_routes

    missing = Account(Paths(tmp_path)).search(_query())
    assert isinstance(missing, SearchRefused)
    assert not (tmp_path / "snapshots").exists()

    (tmp_path / "cookies.txt").write_text("# Netscape HTTP Cookie File\n\n")
    book = parse_routes(FIXTURE.read_text())
    monkeypatch.setattr(
        "seatspy.account.Site.home",
        lambda self: HomePage(logged_in=True, csrf=Csrf("token"), routes=book),
    )
    monkeypatch.setattr("seatspy.account.Site.can_search", lambda self: True)
    dry = Account(Paths(tmp_path)).search(_query(), dry_run=True)
    assert isinstance(dry, SearchDryRun)
    assert not (tmp_path / "snapshots").exists()


def test_diff_never_constructs_site(tmp_path: Path, monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("Site must not be constructed")

    monkeypatch.setattr("seatspy.account.Site", boom)
    monkeypatch.setattr("seatspy.cli.Paths.default", staticmethod(lambda: Paths(tmp_path)))
    outcome = _store(tmp_path).diff(_query())
    assert isinstance(outcome, DiffNoPrevious)
    assert main(DIFF_ARGV) == 0


def test_diff_rejects_dry_run() -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args([*DIFF_ARGV, "--dry-run"])
    assert exc.value.code == 2


def test_partial_coverage_missing_day_is_unknown() -> None:
    previous = _calendar((SEP12, CabinStatus.AVAILABLE))
    current = _calendar(coverage="partial")
    compared = current.changes_since(previous)
    assert isinstance(compared, CalendarChanged)
    assert compared.changes.to_tuple() == (
        StatusChanged(SEP12, CabinStatus.AVAILABLE, CabinStatus.UNKNOWN),
    )
    assert not any(isinstance(item, Vanished) for item in compared.changes.to_tuple())


def test_third_search_ok_keeps_only_last_two(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record(_ok(_calendar((SEP12, CabinStatus.AVAILABLE)), FIRST))
    store.record(_ok(_calendar((SEP13, CabinStatus.AVAILABLE)), SECOND))
    store.record(_ok(_calendar((SEP14, CabinStatus.AVAILABLE)), THIRD))
    outcome = store.diff(_query())
    assert isinstance(outcome, DiffChanged)
    assert outcome.changes.to_tuple() == (
        Vanished(SEP13, CabinStatus.AVAILABLE),
        Appeared(SEP14, CabinStatus.AVAILABLE),
    )
    assert outcome.previous.fetched_at == SECOND
    assert outcome.current.fetched_at == THIRD


def test_diff_help_exists() -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["diff", "--help"])
    assert exc.value.code == 0


def test_doctor_help_list_includes_diff() -> None:
    assert '("login", "quota", "search", "diff")' in DOCTOR.read_text()


def test_cli_zero_and_one_snapshot(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("seatspy.cli.Paths.default", staticmethod(lambda: Paths(tmp_path)))
    assert main(DIFF_ARGV) == 0
    payload = _payload(capsys)
    assert payload["comparison"] == "no_previous_snapshot"
    assert payload["stored"] == 0
    _store(tmp_path).record(_ok(_calendar((SEP12, CabinStatus.AVAILABLE)), FIRST))
    assert main(DIFF_ARGV) == 0
    payload = _payload(capsys)
    assert payload["comparison"] == "no_previous_snapshot"
    assert payload["stored"] == 1


def test_same_fetched_at_replaces_head(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record(_ok(_calendar((SEP12, CabinStatus.AVAILABLE)), FIRST))
    store.record(_ok(_calendar((SEP13, CabinStatus.AVAILABLE)), FIRST))
    outcome = store.diff(_query())
    assert isinstance(outcome, DiffNoPrevious)
    assert outcome.current is not None
    payload = json.loads(outcome.to_json())
    assert payload["stored"] == 1


def test_corrupt_snapshot_is_exit_2(tmp_path: Path, monkeypatch, capsys) -> None:
    store = _store(tmp_path)
    store.record(_ok(_calendar((SEP12, CabinStatus.AVAILABLE)), FIRST))
    files = list((tmp_path / "snapshots").glob("*.json"))
    assert files
    files[0].write_text("{not-json")
    with pytest.raises(SnapshotError):
        store.diff(_query())
    monkeypatch.setattr("seatspy.cli.Paths.default", staticmethod(lambda: Paths(tmp_path)))
    assert main(DIFF_ARGV) == 2
    assert capsys.readouterr().err


def test_snapshots_module_does_not_import_site() -> None:
    source = Path(__file__).resolve().parents[1] / "seatspy" / "snapshots.py"
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "seatspy.site" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "seatspy.site"


def test_window_calendars_compare_pure() -> None:
    previous = _calendar((SEP12, CabinStatus.AVAILABLE), (SEP13, CabinStatus.WAITLIST))
    current = _calendar((SEP13, CabinStatus.WAITLIST), (SEP14, CabinStatus.AVAILABLE))
    compared = current.changes_since(previous)
    assert isinstance(compared, CalendarChanged)
    assert compared.changes.to_tuple() == (
        Vanished(SEP12, CabinStatus.AVAILABLE),
        Appeared(SEP14, CabinStatus.AVAILABLE),
    )
    assert isinstance(previous.changes_since(previous), CalendarUnchanged)


def test_search_ok_records_and_oserror_keeps_calendar(tmp_path: Path, monkeypatch) -> None:
    from seatspy.site import parse_routes

    (tmp_path / "cookies.txt").write_text("# Netscape HTTP Cookie File\n\n")
    book = parse_routes(FIXTURE.read_text())
    monkeypatch.setattr(
        "seatspy.account.Site.home",
        lambda self: HomePage(logged_in=True, csrf=Csrf("token"), routes=book),
    )
    monkeypatch.setattr("seatspy.account.Site.can_search", lambda self: True)
    monkeypatch.setattr("seatspy.account.Site.submit_search", lambda self, csrf, route: SearchPosted())
    monkeypatch.setattr(
        "seatspy.account.Site.year_calendar",
        lambda self, route: YearSnapshot(
            earliest=date(2026, 8, 14),
            latest=date(2027, 8, 3),
            days=(YearDay(SEP12, {Cabin.BUSINESS: CabinStatus.AVAILABLE}),),
        ),
    )
    ok = Account(Paths(tmp_path)).search(_query())
    assert isinstance(ok, SearchOk)
    assert ok.stored is True
    assert json.loads(ok.to_json())["stored"] is True
    assert list((tmp_path / "snapshots").glob("*.json"))

    def fail_record(self, result: SearchOk) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("seatspy.account.SnapshotStore.record", fail_record)
    failed = Account(Paths(tmp_path)).search(_query())
    assert isinstance(failed, SearchOk)
    assert failed.stored is False
    assert failed.message == "Search complete. Snapshot not saved."
    assert failed.calendar.days
