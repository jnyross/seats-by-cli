# AGENTS.md

## Cursor Cloud specific instructions

`seatspy` is a terminal-only Python CLI (no server, no browser on the happy path). It reads SeatSpy credentials from 1Password (`op`) and talks to `https://www.seatspy.com` over HTTP. See `README.md` and `docs/product.md` for the command surface, and `.cursor/skills/verify-seatspy/` for the verification recipes.

### Environment layout (already provisioned by the startup install)

- The virtualenv lives at `.venv` (built with `virtualenv`, not `python -m venv`, because `ensurepip` is unavailable on this image). Always invoke the CLI and tests through `.venv/bin/python`, e.g. `.venv/bin/python -m seatspy ...` and `.venv/bin/python -m pytest`.
- The 1Password CLI `op` is installed to `/usr/local/bin/op`.
- Re-running `bash scripts/cloud-env.sh install` is idempotent: it skips `op` if already on PATH and skips the venv if `import seatspy` already works.

### Lint / test / build / run

- Lint: there is no dedicated linter configured (only `pytest` in `pyproject.toml`). Use `.venv/bin/python -m compileall seatspy tests scripts` as a syntax check.
- Test: `.venv/bin/python -m pytest`. The suite has about 60 tests, runs fully offline, and hits no network.
- Build: editable install only (`pip install -e ".[dev]"`), already done by the startup install.
- Run: `.venv/bin/python -m seatspy <login|quota|search> ...`. Stdout is one JSON object; stderr is one human line. Exit codes: `0` ok, `1` refused, `2` unexpected error.

### Live commands need the 1Password secret

- `login`, and any logged-in `quota`/`search`, need a 1Password service-account token written to `~/.config/seatspy/op-service-account-token`. That file is git-ignored and does not survive into a fresh VM.
- The repo's `start` step (`bash scripts/cloud-env.sh wire`) reads `OP_SERVICE_ACCOUNT_TOKEN`. If that name is unset, it falls back to `ONEPASSWORDSA`. When both names are set, `OP_SERVICE_ACCOUNT_TOKEN` wins.
- Without a token, `login` fails reading 1Password (exit `2`), and `quota`/`search` refuse with `SESSION_MISSING` (exit `1`) because there is no `~/.config/seatspy/cookies.txt`. These refusals are the app working correctly, not a crash.

### Homepage session detection

- `Site.home()` uses an explicit `loggedIn: true|false` marker when SeatSpy emits one.
- The live homepage no longer emits that marker. The fallback treats the navigation as signed in when it has a `/user/account` path and does not have `/auth/sign-in`. Link paths are parsed so absolute URLs, query strings, and trailing slashes keep the same meaning.
- Challenge markers still return `HomeBlocked`, which `quota` and `search` report as `BOT_BLOCKED`.

### Live-drive safety

- Prefer the skill helper `.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature <id> -- <seatspy args>`; it writes evidence under `.verify/runs/` and holds `~/.config/seatspy/live.lock` for the duration. Do not run two live drives at once.
- A non-dry-run `search` spends one of the account's weekly searches. Use `--dry-run` unless you specifically need a live search. Never delete the user's `~/.config/seatspy/cookies.txt`.
