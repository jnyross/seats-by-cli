# SeatSpy CLI

A personal CLI for a SeatSpy account. Stdout is one JSON object. Stderr is one human line.

## Install

```
pip install -e .
```

To run the tests:

```
pip install -e ".[dev]"
python -m pytest
```

If `op` should use a service account, put the token in `~/.config/seatspy/op-service-account-token`. Skip that file when `op` is already signed in.

## Sign in

```
seatspy login
```

Reads the `seatspy.com` item from the `Product Secrets` vault through `op`. Stores the session in `~/.config/seatspy/cookies.txt`. Does not print the password.

## Check quota

```
seatspy quota
seatspy quota --json
```

Asks whether a search is allowed. `--json` is accepted and changes nothing. `can_search` false is a successful read.

## Search

```
seatspy search --airline BA --from LHR --to JFK --direction one-way --cabin business --from-date 2026-09-01 --to-date 2026-09-30 --json
```

Checks the session, quota, and route, then POSTs the search form and reads the year calendar. `--dry-run` stops before the POST.

```
seatspy search --airline BA --from LHR --to JFK --direction one-way --cabin business --from-date 2026-09-01 --to-date 2026-09-30 --dry-run --json
```

## Exit codes

`0` ok, `1` refused, `2` unexpected error.
