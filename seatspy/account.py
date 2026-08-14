from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from seatspy.credentials import read_login
from seatspy.session import SessionStore
from seatspy.snapshots import SnapshotError, SnapshotStore
from seatspy.site import (
    HomeBlocked,
    SearchBlocked,
    SearchExpired,
    SearchPosted,
    SignInBlocked,
    SignInOk,
    Site,
)
from seatspy.types import (
    Calendar,
    CalendarHow,
    LoginOk,
    LoginOutcome,
    LoginRefused,
    Meta,
    Paths,
    Provenance,
    Query,
    QuotaOk,
    QuotaOutcome,
    QuotaRefused,
    Refusal,
    RefusalCode,
    RouteMiss,
    SearchDryRun,
    SearchHow,
    SearchOk,
    SearchOutcome,
    SearchRefused,
    Stage,
    YearIncomplete,
)

_AUTH_FAILED = Refusal(RefusalCode.AUTH_FAILED, "Sign-in failed.")
_BOT_BLOCKED = Refusal(RefusalCode.BOT_BLOCKED, "SeatSpy asked for a challenge. No retry.")
_SESSION_MISSING = Refusal(RefusalCode.SESSION_MISSING, "No saved session. Run seatspy login.")
_SESSION_EXPIRED = Refusal(RefusalCode.SESSION_EXPIRED, "Session expired. Run seatspy login.")
_AIRLINE_INVALID = Refusal(RefusalCode.AIRLINE_INVALID, "Airline is not in SeatSpy's route table.")
_ROUTE_UNSUPPORTED = Refusal(RefusalCode.ROUTE_UNSUPPORTED, "SeatSpy does not serve that route.")
_QUOTA_EXHAUSTED = Refusal(RefusalCode.QUOTA_EXHAUSTED, "No searches left this week.")
_PARSE_FAILED = Refusal(RefusalCode.PARSE_FAILED, "Year calendar did not complete.")
_ROUTE_PARSE_FAILED = Refusal(RefusalCode.PARSE_FAILED, "Route table could not be read.")
_CSRF_PARSE_FAILED = Refusal(RefusalCode.PARSE_FAILED, "Search form token could not be read.")
_SOURCE = "https://www.seatspy.com"


class Account:
    def __init__(self, paths: Paths | None = None) -> None:
        self.paths = paths or Paths.default()

    @staticmethod
    def default() -> Account:
        return Account(Paths.default())

    def login(self) -> LoginOutcome:
        email, password = read_login(self.paths.op_token)
        site = Site(self.paths.cookies)
        result = site.sign_in(email, password)
        if isinstance(result, SignInBlocked):
            return LoginRefused(_BOT_BLOCKED)
        if not isinstance(result, SignInOk):
            return LoginRefused(_AUTH_FAILED)
        SessionStore(self.paths.cookies).replacement(site.jar)
        return LoginOk()

    def quota(self) -> QuotaOutcome:
        if not self.paths.cookies.exists():
            return QuotaRefused(_SESSION_MISSING)
        site = Site(self.paths.cookies)
        home = site.home()
        if isinstance(home, HomeBlocked):
            return QuotaRefused(_BOT_BLOCKED)
        if not home.logged_in:
            return QuotaRefused(_SESSION_EXPIRED)
        return QuotaOk(site.can_search())

    def search(self, query: Query, *, dry_run: bool = False) -> SearchOutcome:
        if not self.paths.cookies.exists():
            return _refuse(query, _SESSION_MISSING, Stage.SESSION, consumed=False)
        site = Site(self.paths.cookies)
        home = site.home()
        if isinstance(home, HomeBlocked):
            return _refuse(query, _BOT_BLOCKED, Stage.SESSION, consumed=False)
        if not home.logged_in:
            return _refuse(query, _SESSION_EXPIRED, Stage.SESSION, consumed=False)
        if not site.can_search():
            return _refuse(query, _QUOTA_EXHAUSTED, Stage.QUOTA, consumed=False)
        if home.routes is None:
            return _refuse(query, _ROUTE_PARSE_FAILED, Stage.UNKNOWN, consumed=False)
        resolved = home.routes.resolve(query)
        if resolved is RouteMiss.AIRLINE_UNKNOWN:
            return _refuse(query, _AIRLINE_INVALID, Stage.ROUTE, consumed=False)
        if isinstance(resolved, RouteMiss):
            return _refuse(query, _ROUTE_UNSUPPORTED, Stage.ROUTE, consumed=False)
        empty = Calendar("window", ())
        if dry_run:
            return SearchDryRun(
                query=query,
                provenance=Provenance(SearchHow.DRY_RUN, CalendarHow.NONE),
                calendar=empty,
                meta=_meta(consumed=False),
            )
        if not home.csrf.reveal():
            return _refuse(query, _CSRF_PARSE_FAILED, Stage.UNKNOWN, consumed=False)
        posted = site.submit_search(home.csrf, resolved)
        if isinstance(posted, SearchExpired):
            return _refuse(query, _SESSION_EXPIRED, Stage.SESSION, consumed=False)
        if isinstance(posted, SearchBlocked):
            return _refuse(query, _BOT_BLOCKED, Stage.SEARCHING, consumed=False)
        if not isinstance(posted, SearchPosted):
            return _refuse(query, _PARSE_FAILED, Stage.SEARCHING, consumed=False)
        try:
            snapshot = site.year_calendar(resolved)
        except YearIncomplete:
            return _refuse(query, _PARSE_FAILED, Stage.SEARCHING, consumed=True)
        ok = SearchOk(
            query=query,
            provenance=Provenance(SearchHow.HTTP_FORM_POST, CalendarHow.HTTP_PARSE),
            calendar=snapshot.project(query),
            meta=_meta(consumed=True),
        )
        try:
            SnapshotStore(self.paths).record(ok)
        except (OSError, SnapshotError):
            return replace(ok, stored=False)
        return ok


def _meta(*, consumed: bool) -> Meta:
    return Meta(datetime.now(timezone.utc), _SOURCE, consumed)


def _refuse(query: Query, refusal: Refusal, stage: Stage, *, consumed: bool) -> SearchRefused:
    return SearchRefused(query=query, refusal=refusal, meta=_meta(consumed=consumed), stage=stage)
