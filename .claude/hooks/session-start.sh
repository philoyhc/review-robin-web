#!/bin/bash
# SessionStart hook: build the Python 3.12 virtualenv the pre-PR gate needs.
#
# CLAUDE.md, "Where work runs": the agent's session container is the gate —
# `pytest -n auto` and `ruff check .` must both pass here before pushing, and
# the install belongs in whatever step has network. That step is this one.
#
# The image ships a `pytest` and a `ruff` as uv tools, but that `pytest` is an
# isolated environment with no `fastapi`, `httpx`, `alembic` or `pytest-xdist`,
# so it cannot collect this suite at all. Its `python3` is also older than the
# >=3.12 floor `pyproject.toml` pins. So this resolves a 3.12+ interpreter
# explicitly, builds `.venv/` from it, installs `pip install -e .[dev]`, and
# puts `.venv/bin` on PATH for the session via $CLAUDE_ENV_FILE.
set -euo pipefail

# Web sessions only; a local checkout keeps whatever venv its owner made.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_DIR"

VENV="$PROJECT_DIR/.venv"
MIN_VERSION_CHECK='import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'

# pyproject.toml pins requires-python = ">=3.12"; prefer an exact 3.12 and
# accept anything newer, rather than trusting whatever `python3` happens to be.
find_python() {
  local candidate resolved
  for candidate in python3.12 python3.13 python3; do
    resolved="$(command -v "$candidate" 2>/dev/null)" || continue
    if "$resolved" -c "$MIN_VERSION_CHECK" 2>/dev/null; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done
  return 1
}

if ! PYTHON="$(find_python)"; then
  echo "session-start: no Python 3.12+ interpreter found; cannot build .venv"
  echo "session-start: no Python 3.12+ interpreter found; cannot build .venv" >&2
  exit 1
fi

# Idempotent: reuse a cached .venv, rebuild only when it is missing, below the
# floor, or broken. Without the pip probe, a 3.12 venv whose pip is unusable
# fails the install on every future session with no path back to a rebuild.
if [ ! -x "$VENV/bin/python" ] \
  || ! "$VENV/bin/python" -c "$MIN_VERSION_CHECK" 2>/dev/null \
  || ! "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
  rm -rf "$VENV"
  "$PYTHON" -m venv "$VENV"
fi

# Export BEFORE installing, not after. Under `set -e` a failed install aborts
# the script, and an export placed after it would then be skipped — leaving the
# session with a perfectly good cached .venv that nothing points at, silently
# back on the image's older python. That is the exact gate failure this hook
# exists to prevent, so the export must not depend on the network succeeding.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$VENV\""
    echo "export PATH=\"$VENV/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
else
  # Say it rather than pass by not doing it: without this file the venv is
  # built and unreachable, and every later command silently uses the wrong one.
  echo "session-start: WARNING: CLAUDE_ENV_FILE unset — .venv/bin is NOT on PATH;"
  echo "session-start:          run 'source .venv/bin/activate' before pytest or ruff."
fi

"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -e ".[dev]"

# tests/integration/test_inline_scripts_parse.py skips silently without node —
# the suite's only tool-gated skip, so say it out loud rather than pass by not
# running. On stdout, because that is what reaches the session; stderr may not.
if ! command -v node >/dev/null 2>&1; then
  echo "session-start: WARNING: node not found — test_inline_scripts_parse.py will skip"
fi

echo "session-start: $("$VENV/bin/python" --version), $("$VENV/bin/python" -m pytest --version 2>&1 | head -1) ready in .venv"
