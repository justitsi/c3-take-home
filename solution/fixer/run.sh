#!/bin/sh
set -eu

# The grader supplies the case directory. Keep the current directory for local
# process runs that do not set C3_WORKSPACE; Docker defaults to /workspace.
FIXER_SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${C3_WORKSPACE:-}" ]; then
    cd "$C3_WORKSPACE"
fi

# Replace the shell so SIGTERM reaches the controller without a shell delay.
exec python3 "$FIXER_SCRIPT_DIR/fix.py"
