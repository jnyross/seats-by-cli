# Login

Login signs John into seatspy.com through `op` and stores only a cookie jar. It never prints the password.

## Sub-features

- `login-help` shows the login usage line.
- `login-ok` POSTs `/auth/sign-in` and writes `~/.config/seatspy/cookies.txt`.
- `login-auth-failed` stays exit 1 with `AUTH_FAILED` when the login form remains.
- `login-bot-blocked` stays exit 1 with `BOT_BLOCKED` when SeatSpy shows a challenge.

## How to get to it (user POV)

- Run `seatspy login`.
- Run `seatspy login --json`. `--json` is accepted and changes nothing.

## Driving it with verify-run

Preconditions:

- Doctor reports `ok` true.
- `~/.config/seatspy/op-service-account-token` exists, or desktop `op` is already signed in.
- No other live drive holds `.verify/live.lock`.

- **Help.** Show usage. Run `.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature login-help -- login --help`. Exit code `0` is not required from the helper (help is not JSON). `stderr.txt` or `stdout.txt` contains `usage: seatspy login`.
- **Sign in.** Store a session. Run `.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature login-ok -- login --json`. `summary.json` has `schema` `seatspy.login.v1`, `status` `ok`, `stored` true, `exit_code` `0`, and `cookies_exist_after` true.
- **Proof.** Read `summary.json` and `stderr.txt`. Stderr is `Signed in.` Do not open `cookies.txt` in evidence.

## Gotchas

- Login replaces the shared jar. A failed login must leave a previous working jar in place. Do not delete the jar to "reset" unless the recipe is proving `SESSION_MISSING` on quota or search.
- Help writes usage to stdout and is not a JSON envelope. Do not require `stdout.json` for `login-help`.
- Never pass `--reveal` output or item field values into chat or evidence.
