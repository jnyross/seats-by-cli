# SeatSpy CLI

A personal CLI for John's SeatSpy account. An agent calls it instead of driving seatspy.com in a browser.

SeatSpy finds airline reward seats. It does not book. Booking stays on the airline site.

There is no public SeatSpy API. Search is a form POST to `/reward-seat-availability`. A few JSON helpers exist, including `/api/can-search-availability`. v1 talks to those. It does not invent a search API.

## Who it is for

John, and any agent running on his machine. Not a public scraper. Not a republisher of SeatSpy calendars.

## v1 path

British Airways, LHR to JFK, one-way, business in September 2026.

```
seatspy login
seatspy quota --json
seatspy search --airline BA --from LHR --to JFK --direction one-way --cabin business --from-date 2026-09-01 --to-date 2026-09-30 --json
```

`login` pulls username and password from the 1Password vault item `seatspy.com` in vault `Product Secrets` through `op`. It never prints those values. It POSTs SeatSpy's own `/auth/sign-in` form and stores only the session. A scripted browser opens only if that POST still leaves the login form up, or if SeatSpy asks for MFA or a captcha.

`quota` calls `/api/can-search-availability` and prints JSON. It does not search.

`search` still runs that quota check itself, then:

1. Fails if there is no session.
2. Loads a fresh CSRF token from the homepage.
3. Calls `/api/can-search-availability`. Stops if the account cannot search.
4. Checks the route against SeatSpy's own airport list for that airline.
5. POSTs the public search form. Place fields are SeatSpy numeric IDs, not raw IATA strings. The CLI maps `--from` / `--to` through the homepage route dictionary. For BA, POST the city place IDs (LON=657, NYC=633), not the airport IDs (LHR=56, JFK=215). Year-data rejects the airport IDs. A fresh-login chain proved the form accepts those city IDs too.
6. Loads the year calendar from `/api/request-year-data` then poll `/api/retrieve-year-data`. `direction` is `outbound` or `inbound`, not `one-way`. Send the same city IDs as the form.
7. If that JSON never completes, read the calendar DOM once with a scripted browser and the saved session. Not an LLM browser.
8. Filters `--from-date` / `--to-date` / `--cabin` on the returned year. Prints one JSON object on stdout.

`--dry-run` stops after step 4 and does not POST. A successful live search writes the projected calendar under `~/.config/seatspy/snapshots/`. Dry-run and refused searches do not.

## Diff

`diff` uses the same query flags as `search`. It does not take `--dry-run`. It never constructs `Site`, never POSTs, and never reads cookies.

```
seatspy diff --airline BA --from LHR --to JFK --direction one-way --cabin business --from-date 2026-09-01 --to-date 2026-09-30 --json
```

The command reads the last two `SearchOk` calendars for that exact `Query` from `~/.config/seatspy/snapshots/`. The filename is the SHA-256 of the canonical `Query.to_dict()` JSON. A different cabin, airport, or date window is a different file.

`status` is always `ok`. `refusal` is always null. Exit is `0`. `meta.search_consumed` is false. `meta.source` is `local_snapshots`.

`comparison` is the discriminator.

- `no_previous_snapshot` when the store has 0 or 1 snapshot. `snapshots.previous` is null. `snapshots.current` is null when `stored` is `0`. `changes` is `[]`. Stderr says to run `search` twice, or once more if one snapshot is already there.
- `unchanged` when two snapshots exist and no day moved.
- `changed` when two snapshots exist and at least one day appeared, vanished, or changed status.

A vanished day is a date that had `available`, `waitlist`, or `unknown` and that `YearSnapshot.project` dropped because the cabin went to `none`. A missing date under `partial` coverage is `unknown`, not `vanished`.

```json
{
  "schema": "seatspy.diff.v1",
  "status": "ok",
  "query": {
    "airline": "BA",
    "origin": "LHR",
    "destination": "JFK",
    "direction": "one-way",
    "cabin": "business",
    "from_date": "2026-09-01",
    "to_date": "2026-09-30"
  },
  "comparison": "changed",
  "snapshots": {
    "previous": {"fetched_at": "2026-08-14T10:00:00Z", "coverage": "window"},
    "current": {"fetched_at": "2026-08-14T18:00:00Z", "coverage": "window"}
  },
  "changes": [
    {"date": "2026-09-12", "change": "appeared", "before": "none", "after": "available"},
    {"date": "2026-09-13", "change": "vanished", "before": "available", "after": "none"},
    {"date": "2026-09-14", "change": "status_changed", "before": "available", "after": "waitlist"}
  ],
  "stored": 2,
  "meta": {"search_consumed": false, "source": "local_snapshots"},
  "refusal": null
}
```

## Access

Hybrid. 1Password plus HTTP for login, quota, search, and year data. Scripted browser only if login or year-data JSON fails.

Do not bypass weekly caps, paywalls, or bot checks. Do not retry a blocked search in a loop.

## What v1 does

One route, one search, one snapshot. A quota command that does not spend a search. A diff command that compares the last two snapshots for the same query without talking to SeatSpy. Optional date window and cabin filter. Structured JSON an agent can parse without a screenshot.

## What v1 refuses

- Booking
- Alerts, Where Can I Go, search history
- Return trips
- Anonymous search
- Partner or multi-stop itineraries SeatSpy does not track
- Republishing or bulk export of calendars
- Calling seats.aero or any other award API
- Printing passwords, cookies, or CSRF tokens

## Output

Stdout is JSON. Stderr is human text.

```json
{
  "schema": "seatspy.search.v1",
  "status": "ok",
  "query": {
    "airline": "BA",
    "origin": "LHR",
    "destination": "JFK",
    "direction": "one-way",
    "cabin": "business",
    "from_date": "2026-09-01",
    "to_date": "2026-09-30"
  },
  "preflight": {
    "session_valid": true,
    "can_search": true,
    "route_supported": true
  },
  "provenance": {
    "search": "http_form_post",
    "calendar": "http_parse"
  },
  "calendar": {
    "coverage": "window",
    "days": [
      {
        "date": "2026-09-12",
        "cabins": [
          { "name": "business", "status": "available" }
        ]
      }
    ]
  },
  "meta": {
    "fetched_at": "2026-08-14T10:00:00Z",
    "source": "https://www.seatspy.com",
    "search_consumed": true
  },
  "stored": true,
  "refusal": null
}
```

`status` is `ok` or `refused`.

`provenance.calendar` is `http_parse` or `browser_extract`.

Cabin `status` is `available`, `none`, `waitlist`, or `unknown`. Year-data flights carry `economy`, `premium`, `business`, and `first` as integers. Treat `> 0` as `available` and `0` as `none`. Other values are `unknown` until a waitlist encoding is seen. Day dates are `dates[].startDate` strings like `Sat, 15 Aug 2026 00:00:00 GMT`. Cover the asked window with `earliestDate` / `latestDate` (`2026/08/14`).

`coverage` is `window` when the asked dates are fully present, else `partial`.

Refusal codes: `SESSION_MISSING`, `SESSION_EXPIRED`, `QUOTA_EXHAUSTED`, `ROUTE_UNSUPPORTED`, `AIRLINE_INVALID`, `BOT_BLOCKED`, `PARSE_FAILED`, `AUTH_FAILED`.

Exit codes: `0` ok, `1` refused, `2` unexpected error.

Empty `days` with `status: ok` means the search ran and nothing matched.

## First spike

Before more commands, prove one logged-in search.

Spike on 2026-08-14 (throwaway, `.audit/spike/`):

1. `op` read the item. Username length 17, password length 20. Values not printed.
2. HTTP POST to `/auth/sign-in` landed on the homepage. `/user/account/` returned 200. `jsData.loggedIn` and `subscriber` were true. No browser.
3. `GET /api/can-search-availability?num_searches=1` returned `{"Result": true}`.
4. `POST /reward-seat-availability` returned the calendar page. Day cells are not in that HTML. The page then calls `/api/request-year-data` and polls `/api/retrieve-year-data`.
5. `POST /api/request-year-data` with city IDs LON=657 NYC=633 returned 202 and `tokens`. The same body with LHR=56 JFK=215 returned 400 `Invalid flight route`.
6. `POST /api/retrieve-year-data` with those tokens returned `status: Completed` and a year object: 349 days, cabins `economy|premium|business|first`, per-flight integer seat counts.
7. One script, one fresh login, no leftover cookies. Form POST BA 657/633, then year-data on that session, then one day mapped to `seatspy.search.v1`. 2026-09-01 had 11 flights. Economy and first none. Premium 9 of 11 with seats. Business 8 of 11. Search is ready to implement.

Build unknowns are in `.audit/spike/UNKNOWNS.md`. The happy path is HTTP. Do not go back to AI browsing.

## Later

- Return trips
- Alerts
- Where Can I Go
- A named-ask file if flag search gets painful
