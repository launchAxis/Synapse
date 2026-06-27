#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BIN="$ROOT/bin"
mkdir -p "$BIN"
printf '%s
' '#!/bin/sh' 'ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)' 'cd "$ROOT" || exit 1' 'npm start -- "$@"' > "$BIN/synapse"
cp "$BIN/synapse" "$BIN/synapse-tui"
chmod +x "$BIN/synapse" "$BIN/synapse-tui"
echo "Add this to PATH if needed: $BIN"
echo "Example: export PATH=\"$BIN:\$PATH\""