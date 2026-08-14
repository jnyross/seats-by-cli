# Search

Search checks session, quota, and route, then either stops (`--dry-run`) or POSTs the form and reads year-data. John types IATA. The CLI POSTs city place IDs.

## Sub-features

- `search-help` shows the required flags.
- `search-dry-run` stops before the form POST. `search_consumed` is false.
- `search-live` POSTs BA LHR-JFK and returns September days for the asked cabin.
- `search-missing` returns `SESSION_MISSING` when the jar is absent.
- `search-route` returns `ROUTE_UNSUPPORTED` for a pair SeatSpy does not serve, without POSTing.

## How to get to it (user POV)

- Run `seatspy search --airline BA --from LHR --to JFK --direction one-way --cabin business --from-date 2026-09-01 --to-date 2026-09-30 --json`.
- Add `--dry-run` to stop after session, quota, and route.

## Driving it with verify-run

Preconditions:

- Doctor reports `ok` true.
- For dry-run and live, `cookies_exist` is true and quota `can_search` is true.
- No other live drive holds the lock.
- Use the BA LHR-JFK September 2026 window unless the recipe names another query.

- **Help.** Show flags. Run `.venv/bin/python -m seatspy search --help`. Exit 0. Usage lists `--airline`, `--from`, `--to`, `--direction`, `--cabin`, `--from-date`, `--to-date`, `--dry-run`.
- **Dry-run.** Check without spending. Run `.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature search-dry-run -- search --airline BA --from LHR --to JFK --direction one-way --cabin business --from-date 2026-09-01 --to-date 2026-09-30 --dry-run --json`. `summary.json` has `schema` `seatspy.search.v1`, `status` `ok`, `exit_code` `0`, `search_consumed` false, `day_count` `0`. `stdout.json` provenance is `search=dry_run` and `calendar=none`.
- **Live search.** Spend one search only when this id is requested. Run the same argv without `--dry-run` and `--feature search-live`. `summary.json` has `status` `ok`, `search_consumed` true, `coverage` `window` or `partial`, and a `day_count`. Assert counts from `summary.json`. Do not paste `calendar.days` into chat.
- **Unserved pair.** Refuse before POST. Run `.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature search-route -- search --airline BA --from JFK --to JNB --direction one-way --cabin business --from-date 2026-09-01 --to-date 2026-09-30 --dry-run --json`. `refusal_code` is `ROUTE_UNSUPPORTED`, `exit_code` is `1`, `search_consumed` is false.
- **Proof.** Keep the run directory. For live search, `day_count` and first/last dates in `stdout.json` are enough.

## Gotchas

- `--dry-run` still hits the homepage and quota. It is not offline.
- A full search spends a weekly search. Do not loop it.
- BA LHR and JFK must resolve to city ids 657 and 633. Airport ids 56 and 215 400 year-data. Offline proof of that map is `tests/test_search.py`. Live proof is a successful year-data envelope, not those numbers in stdout.
- Empty `days` with `status` `ok` means the search ran and nothing matched. That is not a refusal.
- Invalid `--cabin` or a reversed date window is exit 2 from argparse or `Query.parse`, not a refusal envelope.
