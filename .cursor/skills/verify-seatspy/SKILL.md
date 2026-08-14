---
name: verify-seatspy
description: Drive the seatspy CLI the way John or an agent does (login, quota, search) and capture JSON, exit codes, and session side effects. Use when proving SeatSpy CLI behavior, verifying a command after a change, or checking login, quota, or search against the live site.
---

# Verify seatspy

Primary surface is the `seatspy` CLI. Stdout is one JSON object. Stderr is one human line. Exit `0` ok, `1` refused, `2` unexpected. There is no server and no browser on the happy path.

Live commands share `~/.config/seatspy/cookies.txt`. Do not run two live drives at once. `scripts/run.py` holds `~/.config/seatspy/live.lock` for the duration of one command. If doctor reports an alive lock, stop. On cloud agents, login reads `OP_SERVICE_ACCOUNT_TOKEN` first and falls back to `ONEPASSWORDSA`.

Read [features/README.md](features/README.md) before driving. A proof that hits one convenient command is incomplete when the map lists other entry points.

## Launch

No long-lived process. Install once, then each drive is its own CLI process.

```
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Ready when `.venv/bin/python -m seatspy login --help` exits 0.

Teardown is process exit. Do not kill by name. Do not delete `~/.config/seatspy/cookies.txt`.

## Doctor

```
.venv/bin/python .cursor/skills/verify-seatspy/scripts/doctor.py
```

Worth driving when `ok` is true, `import_ok` is true, and `help.login`, `help.quota`, and `help.search` are 0. `cookies_exist` false means live quota and search will refuse `SESSION_MISSING` until login. `live_lock.alive` true means another drive owns the jar. Stop.

Doctor never prints the 1Password token or cookie values. It reports `token_source` (`env:OP_SERVICE_ACCOUNT_TOKEN`, `env:ONEPASSWORDSA`, `file`, or `none`), `token_exist`, and `token_file_exist`. It never reads token file bytes. John adds a Cursor Runtime Secret named `OP_SERVICE_ACCOUNT_TOKEN` (or the existing `ONEPASSWORDSA`). That is a Runtime Secret, not an Environment Variable. There is no `seatspy setup` prompt and nothing copies the secret onto disk. A laptop file and desktop `op` still work.

## Drive

Use the helper. Do not invent argv. Copy the command from the feature file.

```
.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature <id> -- <seatspy-args>
```

Examples:

```
.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature quota-json -- quota --json
.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature search-dry-run -- search --airline BA --from LHR --to JFK --direction one-way --cabin business --from-date 2026-09-01 --to-date 2026-09-30 --dry-run --json
```

The helper prints the run directory path. Assert against `summary.json`, not a pasted calendar.

`--dry-run` still talks to seatspy.com (homepage and quota). It must not POST `/reward-seat-availability`. Prove that by `search_consumed` false and provenance `search=dry_run`. A full search spends a weekly search. Use it only when the map asks for `search-live`.

Never print passwords, cookies, CSRF tokens, or the `op` service-account token. Never copy `cookies.txt` into evidence.

## Evidence

Artifacts land in `.verify/runs/<utc>-<feature>/` and survive cleanup.

| File | What it proves |
|---|---|
| `command.txt` | Exact argv |
| `stdout.txt` / `stdout.json` | The user-visible JSON |
| `stderr.txt` | The human line |
| `exit.txt` | Exit code |
| `summary.json` | schema, status, refusal_code, can_search, stored, search_consumed, day_count, coverage, cookie existence before/after |

Proof standards:

- Drive `python -m seatspy`, not `Account` methods, except pytest which is offline isolation only.
- Capture the command and the resulting envelope. A green pytest run is not a live proof.
- Login side effect is `cookies_exist_after` true and `stored` true. Do not open the jar in evidence.
- After login, quota must return `status` `ok`. `SESSION_EXPIRED` is a failed live proof.
- Quota must not create a search. `search_consumed` is absent on quota envelopes.
- Dry-run must show `search_consumed` false. Live search must show `search_consumed` true and a `day_count`.
- Assert September business availability from `day_count` and first/last dates in `stdout.json` if needed. Do not dump the day list into chat.

## Cleanup

```
rm -f ~/.config/seatspy/live.lock
```

Only remove a lock this run created. Leave `.verify/runs/` in place. Leave the user's cookie jar in place. Leave `.venv` in place.

## Helpers

Both scripts are executable via the venv interpreter shown above.

`scripts/doctor.py` prints one JSON object and exits 0 or 1.

`scripts/run.py --feature <id> -- <args>` runs `python -m seatspy <args>`, writes the run directory, prints that path, exits 0 when stdout was a JSON object.
