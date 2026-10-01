#!/usr/bin/env bash
# PostToolUse hook: format and lint every Python file Claude edits under backend/.
# Problems ruff can't fix itself go back to Claude (exit 2), so it fixes them in its next step.
set -uo pipefail

file=$(jq -r '.tool_input.file_path // empty')
backend="$CLAUDE_PROJECT_DIR/backend"
[[ "$file" == "$backend"/*.py && -f "$file" ]] || exit 0

cd "$backend" || exit 1
# --unfixable F401: an import added in one edit is often only used by the next one, so don't delete it
if ! out=$(uv run --quiet ruff format "$file" 2>&1 >/dev/null &&
    uv run --quiet ruff check --fix --unfixable F401 --quiet --output-format concise "$file" 2>&1); then
    printf 'ruff: problems left in %s\n%s\n' "${file#"$CLAUDE_PROJECT_DIR"/}" "$out" >&2
    exit 2
fi
