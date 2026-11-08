#!/bin/sh
# Describe modules: tools/d.sh '["ModuleA","ModuleB"]'
printf 'globalThis.__names=%s;\n' "$1" > "${TMP:-/tmp}/describe.js"
cat "$(dirname "$0")/describe_modules.js" >> "${TMP:-/tmp}/describe.js"
"$(dirname "$0")/../.venv/Scripts/python" "$(dirname "$0")/probe.py" -f "${TMP:-/tmp}/describe.js"
