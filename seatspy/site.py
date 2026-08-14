from __future__ import annotations

import email.utils
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timezone
from pathlib import Path
from urllib.parse import urlencode

from seatspy.types import (
    Airline,
    Cabin,
    CabinStatus,
    Csrf,
    Iata,
    Password,
    PlaceRow,
    ResolvedRoute,
    RouteBook,
    TransportError,
    YearDay,
    YearIncomplete,
    YearSnapshot,
    cabin_status,
)

_LOGIN_FORM = 'id="login-form"'
_CSRF = re.compile(r'name="csrf_token" value="([^"]+)"')
_BLOCKED = ("g-recaptcha", "h-captcha", "cf-turnstile", "challenge-platform")
_SLASH_DATE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})$")


@dataclass(frozen=True)
class SignInOk:
    pass


@dataclass(frozen=True)
class SignInFormRemained:
    pass


@dataclass(frozen=True)
class SignInBlocked:
    pass


SignInResult = SignInOk | SignInFormRemained | SignInBlocked


@dataclass(frozen=True)
class SearchPosted:
    pass


@dataclass(frozen=True)
class SearchExpired:
    pass


@dataclass(frozen=True)
class SearchBlocked:
    pass


SearchSubmit = SearchPosted | SearchExpired | SearchBlocked


@dataclass(frozen=True)
class HomePage:
    logged_in: bool
    csrf: Csrf = Csrf("")
    routes: RouteBook | None = None


class Site:
    ORIGIN = "https://www.seatspy.com"
    # Empty or Python UA gets a challenge page.
    _UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    def __init__(self, cookies: Path) -> None:
        self._cookies = cookies
        self._jar = http.cookiejar.MozillaCookieJar(str(cookies))
        self._opener: urllib.request.OpenerDirector | None = None

    @property
    def jar(self) -> http.cookiejar.MozillaCookieJar:
        return self._jar

    def sign_in(self, email: str, password: Password) -> SignInResult:
        jar = http.cookiejar.MozillaCookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        _, body, _ = self._request("GET", "/auth/sign-in", opener=opener)
        html = body.decode("utf-8", "replace")
        if _blocked(html):
            return SignInBlocked()
        match = _CSRF.search(html)
        if match is None:
            return SignInFormRemained() if _LOGIN_FORM in html else SignInBlocked()
        form = urlencode(
            {
                "csrf_token": match.group(1),
                "email": email,
                "password": password.reveal(),
                "remember": "y",
            }
        ).encode()
        _, body, _ = self._request(
            "POST",
            "/auth/sign-in",
            data=form,
            referer=f"{self.ORIGIN}/auth/sign-in",
            opener=opener,
        )
        landed = body.decode("utf-8", "replace")
        if _blocked(landed):
            return SignInBlocked()
        if _LOGIN_FORM in landed:
            return SignInFormRemained()
        self._jar = jar
        return SignInOk()

    def home(self) -> HomePage:
        _, body, _ = self._request("GET", "/")
        html = body.decode("utf-8", "replace")
        match = _CSRF.search(html)
        csrf = Csrf(match.group(1)) if match else Csrf("")
        return HomePage(
            logged_in=_LOGIN_FORM not in html,
            csrf=csrf,
            routes=parse_routes(html),
        )

    def can_search(self) -> bool:
        _, body, _ = self._request("GET", "/api/can-search-availability?num_searches=1")
        try:
            payload = json.loads(body.decode("utf-8", "replace"))
        except json.JSONDecodeError as exc:
            raise TransportError("quota response was not JSON") from exc
        result = payload.get("Result") if isinstance(payload, dict) else None
        if not isinstance(result, bool):
            raise TransportError("quota response missing Result")
        return result

    def submit_search(self, csrf: Csrf, route: ResolvedRoute) -> SearchSubmit:
        form = urlencode(
            {
                "csrf_token": csrf.reveal(),
                "airline": route.airline.code,
                "direction": "one-way",
                "outbound": str(route.origin.place_id),
                "inbound": str(route.destination.place_id),
            }
        ).encode()
        status, body, _ = self._request("POST", "/reward-seat-availability", data=form)
        html = body.decode("utf-8", "replace")
        if status == 403 or _blocked(html):
            return SearchBlocked()
        if _LOGIN_FORM in html:
            return SearchExpired()
        return SearchPosted()

    def year_calendar(self, route: ResolvedRoute) -> YearSnapshot:
        payload = {
            "airline_short_codes": [route.airline.code],
            "origin": route.origin.place_id,
            "destination": route.destination.place_id,
            "num_passengers": 1,
            "direction": "outbound",
            "historic_collection_index": 1,
            "attempt": 1,
        }
        _, body, _ = self._request("POST", "/api/request-year-data", json_body=payload)
        try:
            requested = json.loads(body.decode("utf-8", "replace"))
        except json.JSONDecodeError as exc:
            raise YearIncomplete from exc
        tokens = requested.get("tokens") if isinstance(requested, dict) else None
        if not isinstance(tokens, list) or not tokens:
            raise YearIncomplete
        data: object | None = None
        for _ in range(20):
            _, body, _ = self._request(
                "POST",
                "/api/retrieve-year-data",
                json_body={"search_request_ids": tokens},
            )
            try:
                retrieved = json.loads(body.decode("utf-8", "replace"))
            except json.JSONDecodeError as exc:
                raise YearIncomplete from exc
            if not isinstance(retrieved, dict):
                raise YearIncomplete
            if retrieved.get("status") == "Error":
                raise YearIncomplete
            if retrieved.get("status") == "Completed":
                data = retrieved.get("data")
                break
            time.sleep(0.8)
        if not isinstance(data, dict):
            raise YearIncomplete
        return _year_snapshot(data)

    def _session_opener(self) -> urllib.request.OpenerDirector:
        if self._opener is None:
            if self._cookies.exists():
                try:
                    self._jar.load(ignore_discard=True, ignore_expires=True)
                except (OSError, http.cookiejar.LoadError) as exc:
                    raise TransportError("could not read session file") from exc
            self._opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(self._jar)
            )
        return self._opener

    def _request(
        self,
        method: str,
        path: str,
        data: bytes | None = None,
        referer: str | None = None,
        opener: urllib.request.OpenerDirector | None = None,
        json_body: object | None = None,
    ) -> tuple[int, bytes, str]:
        url = f"{self.ORIGIN}{path}"
        headers = {
            "User-Agent": self._UA,
            "Origin": self.ORIGIN,
            "Referer": referer or f"{self.ORIGIN}/",
        }
        body = data
        if json_body is not None:
            body = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
        elif data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        handle = opener or self._session_opener()
        try:
            with handle.open(req, timeout=60) as resp:
                return resp.status, resp.read(), resp.geturl()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), getattr(exc, "url", url)
        except urllib.error.URLError as exc:
            raise TransportError("network error talking to seatspy.com") from exc


def parse_routes(html: str) -> RouteBook | None:
    idx = html.find("newRouteDictionaryAll:")
    start = html.find("{", idx)
    if idx < 0 or start < 0:
        return None
    try:
        raw, _ = json.JSONDecoder().raw_decode(html, start)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    rows: list[PlaceRow] = []
    for airline_code, body in raw.items():
        if airline_code == "$order" or not isinstance(body, dict):
            continue
        try:
            airline = Airline.parse(str(airline_code))
        except ValueError:
            continue
        origins = body.get("origins")
        if not isinstance(origins, dict):
            continue
        for key, origin in origins.items():
            if key == "$order" or not isinstance(origin, dict):
                continue
            row = _place_row(airline, origin)
            if row is not None:
                rows.append(row)
    return RouteBook.from_rows(tuple(rows))


def _place_row(airline: Airline, origin: dict[str, object]) -> PlaceRow | None:
    kind = origin.get("type")
    if kind not in ("city", "airport"):
        return None
    place_id = origin.get("id")
    if not isinstance(place_id, int):
        return None
    primary: Iata | None = None
    raw_iata = origin.get("iata")
    if isinstance(raw_iata, str) and raw_iata.strip():
        try:
            primary = Iata.parse(raw_iata)
        except ValueError:
            primary = None
    iatas: set[Iata] = set()
    raw_iatas = origin.get("iatas")
    if isinstance(raw_iatas, str):
        for part in raw_iatas.split(","):
            token = part.strip()
            if not token:
                continue
            try:
                iatas.add(Iata.parse(token))
            except ValueError:
                continue
    destinations: set[int] = set()
    dest_map = origin.get("destinations")
    if isinstance(dest_map, dict):
        for dest_key, dest in dest_map.items():
            if dest_key == "$order":
                continue
            dest_id = dest.get("id") if isinstance(dest, dict) else None
            if isinstance(dest_id, int):
                destinations.add(dest_id)
                continue
            try:
                destinations.add(int(dest_key))
            except (TypeError, ValueError):
                continue
    order = origin.get("$order")
    return PlaceRow(
        airline=airline,
        place_id=place_id,
        kind=kind,
        iata=primary,
        iatas=frozenset(iatas),
        label=str(origin.get("title") or ""),
        destinations=frozenset(destinations),
        order=order if isinstance(order, int) else 0,
    )


def _year_snapshot(data: dict[str, object]) -> YearSnapshot:
    earliest = _parse_day(data.get("earliestDate"))
    latest = _parse_day(data.get("latestDate"))
    if earliest is None or latest is None:
        raise YearIncomplete
    raw_days = data.get("dates")
    days: list[YearDay] = []
    if isinstance(raw_days, list):
        for raw in raw_days:
            if not isinstance(raw, dict):
                continue
            day = _parse_day(raw.get("startDate"))
            if day is None:
                continue
            flights = raw.get("flights")
            days.append(YearDay(day, _cabin_map(flights if isinstance(flights, list) else [])))
    return YearSnapshot(earliest, latest, tuple(days))


def _cabin_map(flights: list[object]) -> dict[Cabin, CabinStatus]:
    cabins: dict[Cabin, CabinStatus] = {}
    for cabin in Cabin:
        statuses = [
            cabin_status(flight.get(cabin.value))
            for flight in flights
            if isinstance(flight, dict)
        ]
        if any(status is CabinStatus.AVAILABLE for status in statuses):
            cabins[cabin] = CabinStatus.AVAILABLE
        elif statuses and all(status is CabinStatus.NONE for status in statuses):
            cabins[cabin] = CabinStatus.NONE
        else:
            cabins[cabin] = CabinStatus.UNKNOWN
    return cabins


def _parse_day(raw: object) -> date | None:
    if not isinstance(raw, str) or not raw:
        return None
    slash = _SLASH_DATE.fullmatch(raw)
    if slash:
        return date(int(slash.group(1)), int(slash.group(2)), int(slash.group(3)))
    parsed = email.utils.parsedate_to_datetime(raw)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.date()


def _blocked(html: str) -> bool:
    lower = html.lower()
    return any(marker in lower for marker in _BLOCKED)
