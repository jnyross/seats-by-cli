# Quota

Quota asks whether a search is allowed. It does not POST the search form and does not spend a weekly search.

## Sub-features

- `quota-json` returns `seatspy.quota.v1` with `can_search` true or false and exit 0.
- `quota-missing` returns `SESSION_MISSING` and exit 1 when the jar is absent.
- `quota-expired` returns `SESSION_EXPIRED` and exit 1 when the homepage has an explicit `loggedIn: false` marker or its navigation shows `/auth/sign-in`.

## How to get to it (user POV)

- Run `seatspy quota`.
- Run `seatspy quota --json`. `--json` is accepted and changes nothing.

## Driving it with verify-run

Preconditions:

- Doctor reports `ok` true.
- For `quota-json`, `cookies_exist` is true. Run login first if it is not.
- For `quota-missing`, do not delete the user's jar. That path is covered offline by `tests/test_account.py`. Live proof of missing-session uses a machine that has no `cookies.txt`, or skip and say so.

- **JSON read.** Ask whether a search is allowed. Run `.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature quota-json -- quota --json`. `summary.json` has `schema` `seatspy.quota.v1`, `status` `ok`, `exit_code` `0`, and `can_search` a boolean. `search_consumed` is null.
- **False is success.** If `can_search` is false, exit is still `0` and `status` is `ok`. Stderr is `No search available.`
- **True is success.** If `can_search` is true, stderr is `Search available.`
- **Proof.** Keep `stdout.json` and `summary.json`. The envelope has no `calendar` and no `query`.

## Gotchas

- The live homepage currently omits `loggedIn`. Signed-in navigation has `/user/account/` and omits `/auth/sign-in`.
- `can_search` false is not a refusal. Exit 1 with `QUOTA_EXHAUSTED` is a search behavior, not a quota behavior.
- Quota talks to the network. A missing jar is the only offline live miss. Do not invent a second config dir. The CLI has no `--home` flag.
- Do not treat a pytest `SESSION_MISSING` case as a live quota proof.
