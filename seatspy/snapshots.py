from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from seatspy.types import (
    Calendar,
    CalendarChanged,
    CalendarUnchanged,
    DiffChanged,
    DiffNoPrevious,
    DiffOutcome,
    DiffUnchanged,
    Paths,
    Query,
    SearchOk,
    SnapshotRef,
    _iso,
)

_SCHEMA = "seatspy.snapshot-history.v1"
_FILE_KEYS = {"schema", "query", "previous", "current"}
_SNAP_KEYS = {"fetched_at", "calendar"}


class SnapshotError(Exception):
    pass


@dataclass(frozen=True)
class StoredSnapshot:
    fetched_at: datetime
    calendar: Calendar

    @staticmethod
    def from_search(result: SearchOk) -> StoredSnapshot:
        stamp = result.meta.fetched_at.astimezone(timezone.utc).replace(microsecond=0)
        return StoredSnapshot(stamp, result.calendar)

    def to_dict(self) -> dict[str, object]:
        return {"fetched_at": _iso(self.fetched_at), "calendar": self.calendar.to_dict()}

    def as_ref(self) -> SnapshotRef:
        return SnapshotRef(self.fetched_at, self.calendar.coverage)


@dataclass(frozen=True)
class SnapshotHead:
    query: Query
    current: StoredSnapshot


@dataclass(frozen=True)
class SnapshotPair:
    query: Query
    previous: StoredSnapshot
    current: StoredSnapshot


Stored = SnapshotHead | SnapshotPair | None


class SnapshotStore:
    def __init__(self, paths: Paths) -> None:
        self._paths = paths

    def record(self, result: SearchOk) -> None:
        incoming = StoredSnapshot.from_search(result)
        try:
            state = self._load(result.query)
        except SnapshotError:
            state = None
        next_state: SnapshotHead | SnapshotPair
        if state is None:
            next_state = SnapshotHead(result.query, incoming)
        elif isinstance(state, SnapshotHead):
            if state.current.fetched_at == incoming.fetched_at:
                next_state = SnapshotHead(result.query, incoming)
            else:
                next_state = SnapshotPair(result.query, state.current, incoming)
        elif state.current.fetched_at == incoming.fetched_at:
            next_state = SnapshotPair(result.query, state.previous, incoming)
        else:
            next_state = SnapshotPair(result.query, state.current, incoming)
        self._write(next_state)

    def diff(self, query: Query) -> DiffOutcome:
        state = self._load(query)
        if state is None:
            return DiffNoPrevious(query, None)
        if isinstance(state, SnapshotHead):
            return DiffNoPrevious(query, state.current.as_ref())
        compared = state.current.calendar.changes_since(state.previous.calendar)
        previous = state.previous.as_ref()
        current = state.current.as_ref()
        if isinstance(compared, CalendarUnchanged):
            return DiffUnchanged(query, previous, current)
        if not isinstance(compared, CalendarChanged):
            raise SnapshotError("calendar comparison was not a known variant")
        return DiffChanged(query, previous, current, compared.changes)

    def _path_for(self, query: Query) -> Path:
        payload = json.dumps(query.to_dict(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return self._paths.snapshots / f"{digest}.json"

    def _load(self, query: Query) -> Stored:
        path = self._path_for(query)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text())
            body = _file_object(raw)
            stored_query = Query.from_dict(body["query"])
            if stored_query != query:
                raise SnapshotError("snapshot query does not match the file key")
            current = _snapshot(body["current"])
            if body["previous"] is None:
                return SnapshotHead(stored_query, current)
            return SnapshotPair(stored_query, _snapshot(body["previous"]), current)
        except SnapshotError:
            raise
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise SnapshotError("Snapshot file is unreadable.") from exc

    def _write(self, state: SnapshotHead | SnapshotPair) -> None:
        path = self._path_for(state.query)
        previous = None if isinstance(state, SnapshotHead) else state.previous.to_dict()
        body = {
            "schema": _SCHEMA,
            "query": state.query.to_dict(),
            "previous": previous,
            "current": state.current.to_dict(),
        }
        text = json.dumps(body, separators=(",", ":"))
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        tmp = path.with_name(path.name + ".tmp")
        if tmp.exists():
            tmp.unlink()
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)


def _file_object(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError("snapshot file must be an object")
    if set(raw) != _FILE_KEYS:
        raise ValueError("snapshot file keys do not match")
    if raw["schema"] != _SCHEMA:
        raise ValueError("snapshot schema is unknown")
    return raw


def _snapshot(raw: object) -> StoredSnapshot:
    if not isinstance(raw, dict) or set(raw) != _SNAP_KEYS:
        raise ValueError("snapshot keys do not match")
    stamp = _parse_fetched_at(raw["fetched_at"])
    return StoredSnapshot(stamp, Calendar.from_dict(raw["calendar"]))


def _parse_fetched_at(raw: object) -> datetime:
    if not isinstance(raw, str) or not raw.endswith("Z"):
        raise ValueError("fetched_at must be a UTC ISO timestamp")
    return datetime.fromisoformat(raw[:-1] + "+00:00").astimezone(timezone.utc)
