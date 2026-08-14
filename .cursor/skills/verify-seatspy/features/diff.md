# Diff

Diff compares the last two successful searches for an exact query. It reads `~/.config/seatspy/snapshots/` only. It never talks to SeatSpy and never spends a search.

## Sub-features

- `diff-help` shows the same query flags as search and no `--dry-run`.
- `diff-first-run` returns `comparison` `no_previous_snapshot` with `stored` `0` or `1` and exit 0.
- `diff-offline` is proven by `tests/test_diff.py`. Do not POST to seed snapshots.

## How to get to it (user POV)

- Run `seatspy diff --airline BA --from LHR --to JFK --direction one-way --cabin business --from-date 2026-09-01 --to-date 2026-09-30 --json`.
- Use the same flags you used for `search`. There is no `--dry-run`.

## Driving it with verify-run

Preconditions:

- Doctor reports `ok` true.
- No live SeatSpy call is required.
- Do not delete `~/.config/seatspy/snapshots/` or `cookies.txt`.

- **Help.** Show flags. Run `.venv/bin/python -m seatspy diff --help`. Exit 0. Usage lists `--airline`, `--from`, `--to`, `--direction`, `--cabin`, `--from-date`, `--to-date`. Usage does not list `--dry-run`.
- **First run or later.** Read local snapshots. Run `.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature diff-first-run -- diff --airline BA --from LHR --to JFK --direction one-way --cabin business --from-date 2026-09-01 --to-date 2026-09-30 --json`. `summary.json` has `schema` `seatspy.diff.v1`, `status` `ok`, `exit_code` `0`, and `search_consumed` false. `stdout.json` `comparison` is `no_previous_snapshot`, `unchanged`, or `changed`. `meta.source` is `local_snapshots`.
- **Proof.** Keep `stdout.json` and `summary.json`. Offline change kinds live in `tests/test_diff.py`. Do not run a live `search` to manufacture a pair.

## Gotchas

- Diff does not construct `Site` and does not read cookies. A missing jar is irrelevant.
- `--dry-run` on `diff` is an unknown argument and exits 2.
- Zero snapshots is success, not `SESSION_MISSING` and not a new refusal code.
- A different date window is a different query. Snapshots do not overlap.
- Do not spend a weekly search to verify diff.
