# SeatSpy CLI

A personal CLI for a SeatSpy account. Stdout is one JSON object. Stderr is one human line.

## Install

On another machine, install a release wheel, then confirm the version:

```
gh release download v0.1.0 --repo jnyross/seats-by-cli --pattern "*.whl" --dir /tmp
pip install /tmp/seatspy-0.1.0-py3-none-any.whl
seatspy --version
```

`--version` needs no subcommand. It prints the installed PEP 440 version, such as `0.1.0`.

For development, install editable:

```
pip install -e .
```

To cut a release, tag the commit. Do not edit a version field.

```
git tag v0.1.0 && git push origin v0.1.0
```

To run the tests:

```
pip install -e ".[dev]"
python -m pytest
```

If `op` should use a service account, put the token in `~/.config/seatspy/op-service-account-token`. Skip that file when `op` is already signed in. Cloud agents write that file on start from `OP_SERVICE_ACCOUNT_TOKEN`, or from `ONEPASSWORDSA` when the standard name is unset.

On a Cursor Cloud agent, add the token as a Runtime Secret named `OP_SERVICE_ACCOUNT_TOKEN` (or the existing `ONEPASSWORDSA` secret). Use a Runtime Secret, not an Environment Variable, so the value is `[REDACTED]` in tool results and transcripts. There is no `seatspy setup` prompt and nothing copies the secret onto disk. Doctor reports the source kind (`env:OP_SERVICE_ACCOUNT_TOKEN`, `env:ONEPASSWORDSA`, `file`, or `none`). It never prints the value.

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
