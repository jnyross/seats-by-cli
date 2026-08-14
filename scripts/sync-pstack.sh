#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
UPSTREAM_REPO="${PSTACK_UPSTREAM_REPO:-https://github.com/cursor/plugins.git}"
PINNED_SHA="2a8044425c7bddf429c3bdedf3ab61e791d34d65"
sha="${1:-${PSTACK_SHA:-$PINNED_SHA}}"
source_dir="${PSTACK_SOURCE_DIR:-}"
tmpdir=""

cleanup() {
	if [ -n "$tmpdir" ]; then
		rm -rf "$tmpdir"
	fi
}
trap cleanup EXIT

if [ -z "$source_dir" ]; then
	tmpdir="$(mktemp -d)"
	git -C "$tmpdir" init -q
	git -C "$tmpdir" fetch -q --depth 1 "$UPSTREAM_REPO" "$sha"
	git -C "$tmpdir" checkout -q --detach FETCH_HEAD
	source_dir="$tmpdir"
fi

if [ -d "$source_dir/pstack" ]; then
	pstack_dir="$source_dir/pstack"
else
	pstack_dir="$source_dir"
fi

if [ ! -d "$pstack_dir/skills" ] || [ ! -d "$pstack_dir/agents" ]; then
	echo "pstack checkout is missing skills/ or agents/: $pstack_dir" >&2
	exit 1
fi

if [ -d "$source_dir/.git" ]; then
	actual_sha="$(git -C "$source_dir" rev-parse HEAD)"
	if [ "$actual_sha" != "$sha" ]; then
		echo "pstack checkout $actual_sha does not match requested SHA $sha" >&2
		exit 1
	fi
fi

rm -rf "$ROOT/.devin/skills"
mkdir -p "$ROOT/.devin/skills" "$ROOT/.devin/skills/pstack-agents"
cp -a "$pstack_dir/skills/." "$ROOT/.devin/skills/"
cp -a "$pstack_dir/agents/." "$ROOT/.devin/skills/pstack-agents/"

cat >"$ROOT/.devin/skills/pstack-agents/SKILL.md" <<'EOF'
---
name: pstack-agents
description: Reference material for pstack agent roles when adapting pstack workflows to Devin cloud sessions.
---

# Pstack agents

Devin cloud sessions do not have custom subagents. When a request would route to
`poteto-agent` or `comment-sicko`, run the corresponding pstack skill in a
sidekick handoff instead.
EOF

cat >"$ROOT/.devin/skills/PSTACK_UPSTREAM" <<EOF
upstream_repo: $UPSTREAM_REPO
subfolder: pstack
version: 0.14.1
commit: $sha
EOF
