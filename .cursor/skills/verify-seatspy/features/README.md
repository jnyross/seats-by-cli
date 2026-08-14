# SeatSpy verification map

This directory is the maintained source for verifying the user-facing behavior of the seatspy CLI. Read this index before driving, then use the matching feature file as the recipe.

## Baseline preconditions

- Install once with `python3 -m venv .venv` and `.venv/bin/pip install -e ".[dev]"`.
- Run `.venv/bin/python .cursor/skills/verify-seatspy/scripts/doctor.py` and require `ok` true.
- Live commands share `~/.config/seatspy/cookies.txt`. Do not start a second live drive while `.verify/live.lock` is held by a live pid.
- Prefer `--dry-run` for search unless the recipe is `search-live`.
- Drive through `scripts/run.py`. Do not call `Account` for a live proof.

## Driving conventions

- Start from the feature file's preconditions.
- Treat every command as literal. Keep flag names and the BA LHR-JFK September 2026 example unchanged unless the recipe names another query.
- Record the feature id in `--feature`.
- Cleanup removes only `.verify/live.lock`. Proof directories stay.

## Proof and skip reporting

- CLI proof is command, stdout JSON, stderr line, and exit code.
- Login proof includes `cookies_exist_after` true. Do not copy the jar.
- Report an unreachable path with the command and the unmet precondition.
- Do not report a skipped entry point as verified through a different path.

## Features

- [Login](./login.md) covers `seatspy login` and the stored session.
- [Quota](./quota.md) covers `seatspy quota` with and without a session.
- [Search](./search.md) covers dry-run, live search, and route refusal.
