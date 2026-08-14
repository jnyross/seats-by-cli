from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal


class Cabin(Enum):
    ECONOMY = "economy"
    PREMIUM = "premium"
    BUSINESS = "business"
    FIRST = "first"


class CabinStatus(Enum):
    AVAILABLE = "available"
    NONE = "none"
    WAITLIST = "waitlist"
    UNKNOWN = "unknown"


class Direction(Enum):
    ONE_WAY = "one-way"


class RefusalCode(Enum):
    SESSION_MISSING = "SESSION_MISSING"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    ROUTE_UNSUPPORTED = "ROUTE_UNSUPPORTED"
    AIRLINE_INVALID = "AIRLINE_INVALID"
    BOT_BLOCKED = "BOT_BLOCKED"
    PARSE_FAILED = "PARSE_FAILED"
    AUTH_FAILED = "AUTH_FAILED"


class SearchHow(Enum):
    HTTP_FORM_POST = "http_form_post"
    DRY_RUN = "dry_run"


class CalendarHow(Enum):
    HTTP_PARSE = "http_parse"
    NONE = "none"


class Stage(Enum):
    SESSION = "session"
    QUOTA = "quota"
    ROUTE = "route"
    SEARCHING = "searching"
    UNKNOWN = "unknown"


class RouteMiss(Enum):
    AIRLINE_UNKNOWN = "AIRLINE_UNKNOWN"
    PLACE_UNKNOWN = "PLACE_UNKNOWN"
    PAIR_UNKNOWN = "PAIR_UNKNOWN"


STAGE_FOR_CODE: dict[RefusalCode, Stage] = {
    RefusalCode.SESSION_MISSING: Stage.SESSION,
    RefusalCode.SESSION_EXPIRED: Stage.SESSION,
    RefusalCode.AUTH_FAILED: Stage.SESSION,
    RefusalCode.QUOTA_EXHAUSTED: Stage.QUOTA,
    RefusalCode.ROUTE_UNSUPPORTED: Stage.ROUTE,
    RefusalCode.AIRLINE_INVALID: Stage.ROUTE,
    RefusalCode.BOT_BLOCKED: Stage.SEARCHING,
    RefusalCode.PARSE_FAILED: Stage.SEARCHING,
}


def preflight_block(stage: Stage) -> dict[str, bool | None]:
    if stage is Stage.SESSION:
        return {"session_valid": False, "can_search": None, "route_supported": None}
    if stage is Stage.QUOTA:
        return {"session_valid": True, "can_search": False, "route_supported": None}
    if stage is Stage.ROUTE:
        return {"session_valid": True, "can_search": True, "route_supported": False}
    if stage is Stage.SEARCHING:
        return {"session_valid": True, "can_search": True, "route_supported": True}
    return {"session_valid": None, "can_search": None, "route_supported": None}


def cabin_status(seat_count: object) -> CabinStatus:
    if isinstance(seat_count, bool) or not isinstance(seat_count, int):
        return CabinStatus.UNKNOWN
    if seat_count > 0:
        return CabinStatus.AVAILABLE
    if seat_count == 0:
        return CabinStatus.NONE
    return CabinStatus.UNKNOWN


@dataclass(frozen=True)
class Iata:
    code: str

    def __post_init__(self) -> None:
        if len(self.code) != 3 or not self.code.isalpha() or self.code != self.code.upper():
            raise ValueError("IATA must be three uppercase letters")

    @staticmethod
    def parse(raw: str) -> Iata:
        return Iata(raw.strip().upper())

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True)
class Airline:
    code: str

    def __post_init__(self) -> None:
        if not (2 <= len(self.code) <= 3 and self.code.isalnum() and self.code == self.code.upper()):
            raise ValueError("airline must be 2-3 uppercase letters or digits")

    @staticmethod
    def parse(raw: str) -> Airline:
        return Airline(raw.strip().upper())


@dataclass(frozen=True)
class DateWindow:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("from-date must be on or before to-date")

    @staticmethod
    def parse(start: str, end: str) -> DateWindow:
        return DateWindow(date.fromisoformat(start), date.fromisoformat(end))


@dataclass(frozen=True)
class Query:
    airline: Airline
    origin: Iata
    destination: Iata
    direction: Direction
    cabin: Cabin
    window: DateWindow

    def __post_init__(self) -> None:
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")

    @staticmethod
    def parse(
        *,
        airline: str,
        origin: str,
        destination: str,
        direction: str,
        cabin: str,
        from_date: str,
        to_date: str,
    ) -> Query:
        if direction != Direction.ONE_WAY.value:
            raise ValueError("direction must be one-way")
        return Query(
            airline=Airline.parse(airline),
            origin=Iata.parse(origin),
            destination=Iata.parse(destination),
            direction=Direction.ONE_WAY,
            cabin=Cabin(cabin),
            window=DateWindow.parse(from_date, to_date),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "airline": self.airline.code,
            "origin": self.origin.code,
            "destination": self.destination.code,
            "direction": self.direction.value,
            "cabin": self.cabin.value,
            "from_date": self.window.start.isoformat(),
            "to_date": self.window.end.isoformat(),
        }

    @staticmethod
    def from_dict(raw: object) -> Query:
        body = _exact_object(raw, _QUERY_KEYS, "query")
        return Query.parse(
            airline=_text(body["airline"], "airline"),
            origin=_text(body["origin"], "origin"),
            destination=_text(body["destination"], "destination"),
            direction=_text(body["direction"], "direction"),
            cabin=_text(body["cabin"], "cabin"),
            from_date=_text(body["from_date"], "from_date"),
            to_date=_text(body["to_date"], "to_date"),
        )


@dataclass(frozen=True)
class Refusal:
    code: RefusalCode
    message: str


@dataclass(frozen=True)
class Provenance:
    search: SearchHow
    calendar: CalendarHow

    def to_dict(self) -> dict[str, str]:
        return {"search": self.search.value, "calendar": self.calendar.value}


@dataclass(frozen=True)
class Meta:
    fetched_at: datetime
    source: str
    search_consumed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "fetched_at": _iso(self.fetched_at),
            "source": self.source,
            "search_consumed": self.search_consumed,
        }


@dataclass(frozen=True)
class CabinDay:
    name: Cabin
    status: CabinStatus

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name.value, "status": self.status.value}

    @staticmethod
    def from_dict(raw: object) -> CabinDay:
        body = _exact_object(raw, {"name", "status"}, "cabin")
        try:
            name = Cabin(_text(body["name"], "name"))
            status = CabinStatus(_text(body["status"], "status"))
        except ValueError as exc:
            raise ValueError("cabin fields are invalid") from exc
        if status is CabinStatus.NONE:
            raise ValueError("stored cabin status cannot be none")
        return CabinDay(name, status)


@dataclass(frozen=True)
class Day:
    date: date
    cabins: tuple[CabinDay, ...]

    def to_dict(self) -> dict[str, object]:
        return {"date": self.date.isoformat(), "cabins": [cabin.to_dict() for cabin in self.cabins]}

    @staticmethod
    def from_dict(raw: object) -> Day:
        body = _exact_object(raw, {"date", "cabins"}, "day")
        try:
            day = date.fromisoformat(_text(body["date"], "date"))
        except ValueError as exc:
            raise ValueError("day date is invalid") from exc
        cabins_raw = body["cabins"]
        if not isinstance(cabins_raw, list) or len(cabins_raw) != 1:
            raise ValueError("day must carry exactly one cabin")
        return Day(day, (CabinDay.from_dict(cabins_raw[0]),))


@dataclass(frozen=True)
class Appeared:
    date: date
    after: CabinStatus

    def __post_init__(self) -> None:
        if self.after is CabinStatus.NONE:
            raise ValueError("appeared after must not be none")

    def to_dict(self) -> dict[str, str]:
        return {
            "date": self.date.isoformat(),
            "change": "appeared",
            "before": CabinStatus.NONE.value,
            "after": self.after.value,
        }


@dataclass(frozen=True)
class Vanished:
    date: date
    before: CabinStatus

    def __post_init__(self) -> None:
        if self.before is CabinStatus.NONE:
            raise ValueError("vanished before must not be none")

    def to_dict(self) -> dict[str, str]:
        return {
            "date": self.date.isoformat(),
            "change": "vanished",
            "before": self.before.value,
            "after": CabinStatus.NONE.value,
        }


@dataclass(frozen=True)
class StatusChanged:
    date: date
    before: CabinStatus
    after: CabinStatus

    def __post_init__(self) -> None:
        if self.before is CabinStatus.NONE or self.after is CabinStatus.NONE:
            raise ValueError("status change cannot include none")
        if self.before is self.after:
            raise ValueError("status change requires different statuses")

    def to_dict(self) -> dict[str, str]:
        return {
            "date": self.date.isoformat(),
            "change": "status_changed",
            "before": self.before.value,
            "after": self.after.value,
        }


DayChange = Appeared | Vanished | StatusChanged


@dataclass(frozen=True)
class ChangedDays:
    first: DayChange
    rest: tuple[DayChange, ...] = ()

    def to_tuple(self) -> tuple[DayChange, ...]:
        return (self.first, *self.rest)

    def to_list(self) -> list[dict[str, str]]:
        return [item.to_dict() for item in self.to_tuple()]


@dataclass(frozen=True)
class CalendarUnchanged:
    pass


@dataclass(frozen=True)
class CalendarChanged:
    changes: ChangedDays


@dataclass(frozen=True)
class Calendar:
    coverage: Literal["window", "partial"]
    days: tuple[Day, ...]

    def to_dict(self) -> dict[str, object]:
        return {"coverage": self.coverage, "days": [day.to_dict() for day in self.days]}

    @staticmethod
    def from_dict(raw: object) -> Calendar:
        body = _exact_object(raw, {"coverage", "days"}, "calendar")
        coverage = body["coverage"]
        if coverage not in ("window", "partial"):
            raise ValueError("coverage must be window or partial")
        days_raw = body["days"]
        if not isinstance(days_raw, list):
            raise ValueError("days must be a list")
        days = tuple(Day.from_dict(item) for item in days_raw)
        seen = [day.date for day in days]
        if len(seen) != len(set(seen)):
            raise ValueError("calendar dates must be unique")
        return Calendar(coverage, days)

    def changes_since(self, previous: Calendar) -> CalendarUnchanged | CalendarChanged:
        before = _status_by_date(previous)
        after = _status_by_date(self)
        found: list[DayChange] = []
        for day in sorted(set(before) | set(after)):
            left = before.get(day, _missing(previous.coverage))
            right = after.get(day, _missing(self.coverage))
            if left is right:
                continue
            if left is CabinStatus.NONE:
                found.append(Appeared(day, right))
            elif right is CabinStatus.NONE:
                found.append(Vanished(day, left))
            else:
                found.append(StatusChanged(day, left, right))
        if not found:
            return CalendarUnchanged()
        return CalendarChanged(ChangedDays(found[0], tuple(found[1:])))


_QUERY_KEYS = {
    "airline",
    "origin",
    "destination",
    "direction",
    "cabin",
    "from_date",
    "to_date",
}
_DIFF_META = {"search_consumed": False, "source": "local_snapshots"}


def _iso(value: datetime) -> str:
    stamp = value.astimezone(timezone.utc).replace(microsecond=0)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _exact_object(raw: object, keys: set[str], name: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be an object")
    if set(raw) != keys:
        raise ValueError(f"{name} keys do not match")
    return raw


def _text(raw: object, name: str) -> str:
    if not isinstance(raw, str):
        raise ValueError(f"{name} must be a string")
    return raw


def _missing(coverage: Literal["window", "partial"]) -> CabinStatus:
    return CabinStatus.NONE if coverage == "window" else CabinStatus.UNKNOWN


def _status_by_date(calendar: Calendar) -> dict[date, CabinStatus]:
    return {day.date: day.cabins[0].status for day in calendar.days if day.cabins}


def _dump(schema: str, *, refused: bool, refusal: Refusal | None, **fields: object) -> str:
    body: dict[str, object] = {
        "schema": schema,
        "status": "refused" if refused else "ok",
        **fields,
        "refusal": None,
    }
    if refusal is not None:
        body["refusal"] = {"code": refusal.code.value, "message": refusal.message}
    return json.dumps(body)


@dataclass(frozen=True)
class LoginOk:
    schema: Literal["seatspy.login.v1"] = "seatspy.login.v1"
    stored: bool = True

    @property
    def refused(self) -> bool:
        return False

    @property
    def refusal(self) -> Refusal | None:
        return None

    @property
    def exit_code(self) -> int:
        return 0

    @property
    def message(self) -> str:
        return "Signed in."

    def to_json(self) -> str:
        return _dump(self.schema, refused=False, refusal=None, stored=self.stored)


@dataclass(frozen=True)
class LoginRefused:
    refusal: Refusal
    schema: Literal["seatspy.login.v1"] = "seatspy.login.v1"

    @property
    def refused(self) -> bool:
        return True

    @property
    def exit_code(self) -> int:
        return 1

    @property
    def message(self) -> str:
        return self.refusal.message

    def to_json(self) -> str:
        return _dump(self.schema, refused=True, refusal=self.refusal)


@dataclass(frozen=True)
class QuotaOk:
    can_search: bool
    schema: Literal["seatspy.quota.v1"] = "seatspy.quota.v1"

    @property
    def refused(self) -> bool:
        return False

    @property
    def refusal(self) -> Refusal | None:
        return None

    @property
    def exit_code(self) -> int:
        return 0

    @property
    def message(self) -> str:
        return "Search available." if self.can_search else "No search available."

    def to_json(self) -> str:
        return _dump(self.schema, refused=False, refusal=None, can_search=self.can_search)


@dataclass(frozen=True)
class QuotaRefused:
    refusal: Refusal
    schema: Literal["seatspy.quota.v1"] = "seatspy.quota.v1"

    @property
    def refused(self) -> bool:
        return True

    @property
    def exit_code(self) -> int:
        return 1

    @property
    def message(self) -> str:
        return self.refusal.message

    def to_json(self) -> str:
        return _dump(self.schema, refused=True, refusal=self.refusal)


@dataclass(frozen=True)
class SearchOk:
    query: Query
    provenance: Provenance
    calendar: Calendar
    meta: Meta
    stored: bool = True
    schema: Literal["seatspy.search.v1"] = "seatspy.search.v1"

    @property
    def refused(self) -> bool:
        return False

    @property
    def refusal(self) -> Refusal | None:
        return None

    @property
    def exit_code(self) -> int:
        return 0

    @property
    def message(self) -> str:
        return "Search complete." if self.stored else "Search complete. Snapshot not saved."

    def to_json(self) -> str:
        return _dump(
            self.schema,
            refused=False,
            refusal=None,
            query=self.query.to_dict(),
            preflight=preflight_block(Stage.SEARCHING),
            provenance=self.provenance.to_dict(),
            calendar=self.calendar.to_dict(),
            meta=self.meta.to_dict(),
            stored=self.stored,
        )


@dataclass(frozen=True)
class SearchDryRun:
    query: Query
    provenance: Provenance
    calendar: Calendar
    meta: Meta
    schema: Literal["seatspy.search.v1"] = "seatspy.search.v1"

    @property
    def refused(self) -> bool:
        return False

    @property
    def refusal(self) -> Refusal | None:
        return None

    @property
    def exit_code(self) -> int:
        return 0

    @property
    def message(self) -> str:
        return "Dry run. No search spent."

    def to_json(self) -> str:
        return _dump(
            self.schema,
            refused=False,
            refusal=None,
            query=self.query.to_dict(),
            preflight=preflight_block(Stage.SEARCHING),
            provenance=self.provenance.to_dict(),
            calendar=self.calendar.to_dict(),
            meta=self.meta.to_dict(),
        )


@dataclass(frozen=True)
class SearchRefused:
    query: Query
    refusal: Refusal
    meta: Meta
    stage: Stage
    schema: Literal["seatspy.search.v1"] = "seatspy.search.v1"

    @property
    def refused(self) -> bool:
        return True

    @property
    def exit_code(self) -> int:
        return 1

    @property
    def message(self) -> str:
        return self.refusal.message

    def to_json(self) -> str:
        return _dump(
            self.schema,
            refused=True,
            refusal=self.refusal,
            query=self.query.to_dict(),
            preflight=preflight_block(self.stage),
            meta=self.meta.to_dict(),
        )


LoginOutcome = LoginOk | LoginRefused
QuotaOutcome = QuotaOk | QuotaRefused
SearchOutcome = SearchOk | SearchDryRun | SearchRefused


@dataclass(frozen=True)
class SnapshotRef:
    fetched_at: datetime
    coverage: Literal["window", "partial"]

    def to_dict(self) -> dict[str, str]:
        return {"fetched_at": _iso(self.fetched_at), "coverage": self.coverage}


@dataclass(frozen=True)
class DiffNoPrevious:
    query: Query
    current: SnapshotRef | None
    schema: Literal["seatspy.diff.v1"] = "seatspy.diff.v1"

    @property
    def refused(self) -> bool:
        return False

    @property
    def refusal(self) -> Refusal | None:
        return None

    @property
    def exit_code(self) -> int:
        return 0

    @property
    def message(self) -> str:
        if self.current is None:
            return "No snapshot for this query. Run seatspy search twice."
        return "No previous snapshot for this query. Run seatspy search once more."

    def to_json(self) -> str:
        return _dump(
            self.schema,
            refused=False,
            refusal=None,
            query=self.query.to_dict(),
            comparison="no_previous_snapshot",
            snapshots={
                "previous": None,
                "current": None if self.current is None else self.current.to_dict(),
            },
            changes=[],
            stored=0 if self.current is None else 1,
            meta=_DIFF_META,
        )


@dataclass(frozen=True)
class DiffUnchanged:
    query: Query
    previous: SnapshotRef
    current: SnapshotRef
    schema: Literal["seatspy.diff.v1"] = "seatspy.diff.v1"

    @property
    def refused(self) -> bool:
        return False

    @property
    def refusal(self) -> Refusal | None:
        return None

    @property
    def exit_code(self) -> int:
        return 0

    @property
    def message(self) -> str:
        return "No changes since the previous snapshot."

    def to_json(self) -> str:
        return _dump(
            self.schema,
            refused=False,
            refusal=None,
            query=self.query.to_dict(),
            comparison="unchanged",
            snapshots={"previous": self.previous.to_dict(), "current": self.current.to_dict()},
            changes=[],
            stored=2,
            meta=_DIFF_META,
        )


@dataclass(frozen=True)
class DiffChanged:
    query: Query
    previous: SnapshotRef
    current: SnapshotRef
    changes: ChangedDays
    schema: Literal["seatspy.diff.v1"] = "seatspy.diff.v1"

    @property
    def refused(self) -> bool:
        return False

    @property
    def refusal(self) -> Refusal | None:
        return None

    @property
    def exit_code(self) -> int:
        return 0

    @property
    def message(self) -> str:
        count = 1 + len(self.changes.rest)
        return "1 day changed." if count == 1 else f"{count} days changed."

    def to_json(self) -> str:
        return _dump(
            self.schema,
            refused=False,
            refusal=None,
            query=self.query.to_dict(),
            comparison="changed",
            snapshots={"previous": self.previous.to_dict(), "current": self.current.to_dict()},
            changes=self.changes.to_list(),
            stored=2,
            meta=_DIFF_META,
        )


DiffOutcome = DiffNoPrevious | DiffUnchanged | DiffChanged


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def cookies(self) -> Path:
        return self.root / "cookies.txt"

    @property
    def op_token(self) -> Path:
        return self.root / "op-service-account-token"

    @property
    def snapshots(self) -> Path:
        return self.root / "snapshots"

    @staticmethod
    def default() -> Paths:
        return Paths(Path.home() / ".config" / "seatspy")


@dataclass(frozen=True)
class Password:
    _value: str

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"Password(len={len(self._value)})"

    def __str__(self) -> str:
        return f"Password(len={len(self._value)})"


@dataclass(frozen=True)
class Csrf:
    _value: str

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Csrf(<redacted>)"

    def __str__(self) -> str:
        return "Csrf(<redacted>)"


@dataclass(frozen=True)
class CityPlace:
    _place_id: int
    iatas: frozenset[Iata]
    label: str
    destinations: frozenset[int]

    @property
    def place_id(self) -> int:
        return self._place_id


@dataclass(frozen=True)
class AirportPlace:
    _place_id: int
    iata: Iata
    city: CityPlace | None
    label: str
    destinations: frozenset[int]

    @property
    def place_id(self) -> int:
        return self._place_id


@dataclass(frozen=True)
class PlaceRow:
    airline: Airline
    place_id: int
    kind: Literal["city", "airport"]
    iata: Iata | None
    iatas: frozenset[Iata]
    label: str
    destinations: frozenset[int]
    order: int


@dataclass(frozen=True)
class ResolvedRoute:
    airline: Airline
    origin: CityPlace
    destination: CityPlace
    direction: Direction


@dataclass(frozen=True)
class RouteBook:
    _cities: dict[Airline, tuple[CityPlace, ...]]
    _airports: dict[Airline, tuple[AirportPlace, ...]]

    @staticmethod
    def from_rows(rows: tuple[PlaceRow, ...]) -> RouteBook:
        city_rows = sorted((row for row in rows if row.kind == "city"), key=lambda row: row.order)
        cities: dict[Airline, list[CityPlace]] = {}
        by_id: dict[tuple[Airline, int], CityPlace] = {}
        by_city_iata: dict[tuple[Airline, Iata], list[CityPlace]] = {}
        for row in city_rows:
            iatas = set(row.iatas)
            if row.iata is not None:
                iatas.add(row.iata)
            city = CityPlace(row.place_id, frozenset(iatas), row.label, row.destinations)
            cities.setdefault(row.airline, []).append(city)
            by_id[(row.airline, row.place_id)] = city
            if row.iata is not None:
                by_city_iata.setdefault((row.airline, row.iata), []).append(city)
        airports: dict[Airline, list[AirportPlace]] = {}
        airport_rows = sorted((row for row in rows if row.kind == "airport"), key=lambda row: row.order)
        for row in airport_rows:
            if row.iata is None:
                continue
            parent = _parent_city(row, cities.get(row.airline, []), by_city_iata)
            airports.setdefault(row.airline, []).append(
                AirportPlace(row.place_id, row.iata, parent, row.label, row.destinations)
            )
        return RouteBook(
            {airline: tuple(items) for airline, items in cities.items()},
            {airline: tuple(items) for airline, items in airports.items()},
        )

    def city_for(self, airline: Airline, iata: Iata) -> CityPlace | RouteMiss:
        if airline not in self._cities and airline not in self._airports:
            return RouteMiss.AIRLINE_UNKNOWN
        claimed = [city for city in self._cities.get(airline, ()) if iata in city.iatas]
        if claimed:
            return claimed[0]
        for airport in self._airports.get(airline, ()):
            if airport.iata == iata and airport.city is not None:
                return airport.city
        for airport in self._airports.get(airline, ()):
            if airport.iata == iata and airport.city is None:
                return CityPlace(airport.place_id, frozenset({airport.iata}), airport.label, airport.destinations)
        return RouteMiss.PLACE_UNKNOWN

    def resolve(self, query: Query) -> ResolvedRoute | RouteMiss:
        origin = self.city_for(query.airline, query.origin)
        if origin is RouteMiss.AIRLINE_UNKNOWN:
            return origin
        destination = self.city_for(query.airline, query.destination)
        if isinstance(origin, RouteMiss):
            return origin
        if isinstance(destination, RouteMiss):
            return destination
        if destination.place_id not in origin.destinations:
            return RouteMiss.PAIR_UNKNOWN
        return ResolvedRoute(query.airline, origin, destination, query.direction)


def _parent_city(
    row: PlaceRow,
    cities: list[CityPlace],
    by_city_iata: dict[tuple[Airline, Iata], list[CityPlace]],
) -> CityPlace | None:
    if row.iata is None:
        return None
    claimed = [city for city in cities if row.iata in city.iatas]
    if claimed:
        return claimed[0]
    for code in row.iatas:
        parents = by_city_iata.get((row.airline, code), [])
        if parents:
            return parents[0]
    return None


@dataclass(frozen=True)
class YearDay:
    date: date
    cabins: dict[Cabin, CabinStatus]


@dataclass(frozen=True)
class YearSnapshot:
    earliest: date
    latest: date
    days: tuple[YearDay, ...]

    def project(self, query: Query) -> Calendar:
        coverage: Literal["window", "partial"] = (
            "window" if self.earliest <= query.window.start and query.window.end <= self.latest else "partial"
        )
        days: list[Day] = []
        for day in self.days:
            if day.date < query.window.start or day.date > query.window.end:
                continue
            status = day.cabins.get(query.cabin, CabinStatus.UNKNOWN)
            if status is CabinStatus.NONE:
                continue
            days.append(Day(day.date, (CabinDay(query.cabin, status),)))
        return Calendar(coverage, tuple(days))


class TransportError(Exception):
    pass


class YearIncomplete(Exception):
    pass
