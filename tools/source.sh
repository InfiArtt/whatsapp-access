#!/bin/sh
# Print a WhatsApp module's source: tools/source.sh ModuleName [maxChars]
printf 'globalThis.__module="%s"; globalThis.__max=%s;\n' "$1" "${2:-6000}" > "${TMP:-/tmp}/source.js"
cat "$(dirname "$0")/source.js" >> "${TMP:-/tmp}/source.js"
"$(dirname "$0")/../.venv/Scripts/python" "$(dirname "$0")/probe.py" -f "${TMP:-/tmp}/source.js" | sed 's/\n/\n/g; s/\\"/"/g'
