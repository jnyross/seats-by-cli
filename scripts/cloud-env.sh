#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
OP_VER="2.38.1"
OP_ARCH="amd64"
TOKEN_PATH="${HOME}/.config/seatspy/op-service-account-token"

install_op() {
	if command -v op >/dev/null 2>&1; then
		return 0
	fi
	tmpdir="$(mktemp -d)"
	trap 'rm -rf "$tmpdir"' EXIT
	curl -fsSL "https://cache.agilebits.com/dist/1P/op2/pkg/v${OP_VER}/op_linux_${OP_ARCH}_v${OP_VER}.zip" -o "$tmpdir/op.zip"
	python3 -c "import zipfile; zipfile.ZipFile('$tmpdir/op.zip').extract('op', '$tmpdir')"
	chmod 755 "$tmpdir/op"
	if [ -w /usr/local/bin ]; then
		cp "$tmpdir/op" /usr/local/bin/op
	else
		sudo cp "$tmpdir/op" /usr/local/bin/op
	fi
}

install_venv() {
	if [ -x "$ROOT/.venv/bin/python" ]; then
		"$ROOT/.venv/bin/python" -c "import seatspy" >/dev/null 2>&1 && return 0
	fi
	if python3 -c "import ensurepip" >/dev/null 2>&1; then
		python3 -m venv "$ROOT/.venv"
	else
		python3 -m pip install --user virtualenv
		python3 -m virtualenv "$ROOT/.venv"
	fi
	"$ROOT/.venv/bin/pip" install -e "$ROOT[dev]"
}

wire_token() {
	mkdir -p "${HOME}/.config/seatspy"
	chmod 700 "${HOME}/.config/seatspy"
	if [ -z "${OP_SERVICE_ACCOUNT_TOKEN:-}" ]; then
		echo "OP_SERVICE_ACCOUNT_TOKEN is unset. Add that Cursor secret and restart." >&2
		return 0
	fi
	umask 077
	tmp="${TOKEN_PATH}.tmp"
	printf '%s\n' "$OP_SERVICE_ACCOUNT_TOKEN" >"$tmp"
	chmod 600 "$tmp"
	mv "$tmp" "$TOKEN_PATH"
	echo "Wrote service-account token file." >&2
}

case "${1:-}" in
install)
	install_op
	install_venv
	;;
wire)
	wire_token
	;;
*)
	echo "usage: $0 install|wire" >&2
	exit 2
	;;
esac
