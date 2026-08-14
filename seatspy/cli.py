from __future__ import annotations

import argparse
import sys
from importlib import metadata

from seatspy.account import Account
from seatspy.snapshots import SnapshotError, SnapshotStore
from seatspy.types import Paths, Query, TransportError


def _installed_version() -> str:
    try:
        return metadata.version("seatspy")
    except metadata.PackageNotFoundError:
        return "0+unknown"


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", help="Accepted. Stdout is always JSON.")
    query_flags = argparse.ArgumentParser(add_help=False)
    query_flags.add_argument("--airline", required=True, help="Airline code, such as BA.")
    query_flags.add_argument("--from", dest="origin", required=True, help="Origin IATA.")
    query_flags.add_argument("--to", dest="destination", required=True, help="Destination IATA.")
    query_flags.add_argument("--direction", required=True, choices=["one-way"], help="Trip direction.")
    query_flags.add_argument("--cabin", required=True, help="Cabin: economy, premium, business, or first.")
    query_flags.add_argument("--from-date", required=True, help="Window start, YYYY-MM-DD.")
    query_flags.add_argument("--to-date", required=True, help="Window end, YYYY-MM-DD.")
    parser = argparse.ArgumentParser(prog="seatspy")
    parser.add_argument("--json", action="store_true", help="Accepted. Stdout is always JSON.")
    parser.add_argument("--version", action="version", version=_installed_version())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", parents=[shared], help="Sign in and store the session.")
    sub.add_parser("quota", parents=[shared], help="Check whether a search is allowed.")
    search = sub.add_parser("search", parents=[shared, query_flags], help="Search reward seats.")
    search.add_argument("--dry-run", action="store_true", help="Check session, route, and quota. Do not POST.")
    sub.add_parser("diff", parents=[shared, query_flags], help="Compare the last two snapshots for this query.")
    return parser


def _query_from(args: argparse.Namespace) -> Query:
    return Query.parse(
        airline=args.airline,
        origin=args.origin,
        destination=args.destination,
        direction=args.direction,
        cabin=args.cabin,
        from_date=args.from_date,
        to_date=args.to_date,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "diff":
            outcome = SnapshotStore(Paths.default()).diff(_query_from(args))
        elif args.command == "search":
            outcome = Account.default().search(_query_from(args), dry_run=args.dry_run)
        elif args.command == "login":
            outcome = Account.default().login()
        else:
            outcome = Account.default().quota()
    except (TransportError, ValueError, SnapshotError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(outcome.to_json(), flush=True)
    print(outcome.message, file=sys.stderr)
    return outcome.exit_code
