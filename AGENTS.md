# AGENTS.md

## pstack on Devin

pstack is a Cursor plugin. Devin cannot install it (Devin reads `.devin-plugin/plugin.json`, `.claude-plugin/plugin.json`, or a root `plugin.json`; pstack ships only `.cursor-plugin/plugin.json`), so its skills are vendored under `.devin/skills/`, which Devin loads automatically. `scripts/sync-pstack.sh` re-vendors them from the pinned upstream commit. In Cursor nothing changes: the installed plugin still supplies pstack, and `.cursor/skills/` holds only `verify-seatspy`.

The skill text is upstream and unedited, so it speaks Cursor. Read it through this mapping in a Devin session:

- A `/skill-name` reference means the skill of that name. Invoke it with the `skill` tool; there are no slash commands.
- A `Task` subagent means a `sidekick` handoff. There is one persistent sidekick, and Devin cannot pick a model, so `.cursor/rules/pstack-models.mdc` is inert here — the per-role model slugs do not apply and no role runs on a different model.
- `setup-pstack` has nothing to configure here; it writes Cursor model rules. Skip it.
- A multi-model panel (how critics, arena runners, architect runners, interrogate reviewers, arena cross-judge pool) has no same-machine equivalent. Run it either as consecutive sidekick handoffs, each given its own stated stance, or as parallel child sessions via `devin_session_create`. Fan-out counts carry over; the model diversity the panel assumes does not, so say so when reporting a panel's verdict.
- `swarm` workers are child sessions. They get their own machines and do not share this checkout, so a worker needs its own branch and its own setup step.
- `AskQuestion` means `message_user` with `content_type="user_question"`.
- Graphite (`gt`, "the stack") means the `git_stack` tool. Never rebase or merge stacked branches by hand.
- Bugbot and the agentic security review mean Devin Review; its findings arrive as PR comments, read with `git_view_pr`. CI status is `git_pr_checks` and failing logs are `git_ci_job_logs`.
- Opening or updating a PR is `fetch_pr_template` then `git_create_pr` / `git_update_pr`, not `gh pr create`.
- The `cursor-team-kit` skills some playbooks call (`deslop`, `control-cli`, `control-ui`) are not vendored. Use `no-comments` and `unslop` in place of `deslop`, and drive this CLI yourself or through `testing_agent` in place of the control skills. Do not fake a skill that is not present; say it is missing.
- Custom subagent profiles (`poteto-agent`, `comment-sicko`) do not load in cloud sessions. Routing to one means running the matching skill in a sidekick handoff.

Devin's own operating rules win where they conflict: the lead owns user messages, PR creation and updates, secret requests, and starting `testing_agent`, whatever a playbook assigns to a subagent.

## Cursor Cloud specific instructions

`seatspy` is a terminal-only Python CLI (no server, no browser on the happy path). It reads SeatSpy credentials from 1Password (`op`) and talks to `https://www.seatspy.com` over HTTP. See `README.md` and `docs/product.md` for the command surface, and `.cursor/skills/verify-seatspy/` for the verification recipes.

### Environment layout (already provisioned by the startup install)

- The virtualenv lives at `.venv` (built with `virtualenv`, not `python -m venv`, because `ensurepip` is unavailable on this image). Always invoke the CLI and tests through `.venv/bin/python`, e.g. `.venv/bin/python -m seatspy ...` and `.venv/bin/python -m pytest`.
- The 1Password CLI `op` is installed to `/usr/local/bin/op`.
- Re-running `bash scripts/cloud-env.sh install` is idempotent: it skips `op` if already on PATH and skips the venv if `import seatspy` already works.

### Lint / test / build / run

- Lint: there is no dedicated linter configured (only `pytest` in `pyproject.toml`). Use `.venv/bin/python -m compileall seatspy tests scripts` as a syntax check.
- Test: `.venv/bin/python -m pytest`. The suite has about 60 tests, runs fully offline, and hits no network.
- Build: editable install (`pip install -e ".[dev]"`), already done by the startup install. A release wheel is `python -m build` then `scripts/check-wheel.sh dist/*.whl`.
- CI: pytest, compileall, and a wheel smoke. No live SeatSpy, no `op`. Merging to `main` also runs the `release` workflow, which tags the next patch and publishes a GitHub Release.
- Run: `.venv/bin/python -m seatspy <login|quota|search> ...`. Stdout is one JSON object; stderr is one human line. Exit codes: `0` ok, `1` refused, `2` unexpected error. `seatspy --version` is argparse metadata, not a command.

### Live commands need the 1Password secret

- `login` reads a 1Password service-account token from a Cursor Runtime Secret named `OP_SERVICE_ACCOUNT_TOKEN`, or from `ONEPASSWORDSA` when the standard name is unset. Use a Runtime Secret, not an Environment Variable, so the value is `[REDACTED]` in tool results and transcripts. A laptop can still use `~/.config/seatspy/op-service-account-token` or a signed-in desktop `op`.
- Doctor reports `token_source` (`env:OP_SERVICE_ACCOUNT_TOKEN`, `env:ONEPASSWORDSA`, `file`, or `none`). It never prints the value. The start hook `bash scripts/cloud-env.sh wire` may still write the token file. Login does not need that file when the Runtime Secret is present.
- Without a token, `login` fails reading 1Password (exit `2`), and `quota`/`search` refuse with `SESSION_MISSING` (exit `1`) because there is no `~/.config/seatspy/cookies.txt`. These refusals are the app working correctly, not a crash.

### Homepage session detection

- `Site.home()` uses an explicit `loggedIn: true|false` marker when SeatSpy emits one.
- The live homepage no longer emits that marker. The fallback treats the navigation as signed in when it has a `/user/account` path and does not have `/auth/sign-in`. Link paths are parsed so absolute URLs, query strings, and trailing slashes keep the same meaning.
- Challenge markers still return `HomeBlocked`, which `quota` and `search` report as `BOT_BLOCKED`.

### Live-drive safety

- Prefer the skill helper `.venv/bin/python .cursor/skills/verify-seatspy/scripts/run.py --feature <id> -- <seatspy args>`; it writes evidence under `.verify/runs/` and holds `~/.config/seatspy/live.lock` for the duration. Do not run two live drives at once.
- A non-dry-run `search` spends one of the account's weekly searches. Use `--dry-run` unless you specifically need a live search. Never delete the user's `~/.config/seatspy/cookies.txt`.
