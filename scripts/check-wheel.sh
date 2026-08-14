#!/bin/sh
set -eu

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
	echo "usage: $0 WHEEL [EXPECTED]" >&2
	exit 2
fi

if [ "$(git rev-parse --is-shallow-repository)" != false ]; then
	echo "shallow checkout: git describe is unreliable here; set fetch-depth: 0" >&2
	exit 1
fi

WHEEL="$1"
EXPECTED="${2:-}"

venv="$(mktemp -d)"
trap 'rm -rf "$venv"' EXIT

if python3 -c "import ensurepip" >/dev/null 2>&1; then
	python3 -m venv "$venv"
else
	python3 -m pip install --user virtualenv
	python3 -m virtualenv "$venv"
fi

"$venv/bin/pip" install --quiet "$WHEEL"
"$venv/bin/seatspy" --help >/dev/null
got="$("$venv/bin/seatspy" --version)"
if [ -n "$EXPECTED" ] && [ "$got" != "$EXPECTED" ]; then
	echo "version $got != $EXPECTED" >&2
	exit 1
fi
