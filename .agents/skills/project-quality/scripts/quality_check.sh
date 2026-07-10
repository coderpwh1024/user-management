#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT_DIR" || exit 1

status=0

pick_python() {
    candidates=()
    if [ -n "${QUALITY_PYTHON:-}" ]; then
        candidates+=("$QUALITY_PYTHON")
    fi
    candidates+=(".venv/bin/python")
    if command -v python3 >/dev/null 2>&1; then
        candidates+=("$(command -v python3)")
    fi
    if command -v python >/dev/null 2>&1; then
        candidates+=("$(command -v python)")
    fi

    for candidate in "${candidates[@]}"; do
        if [ -x "$candidate" ] || command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >/dev/null 2>&1; then
                printf '%s\n' "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

run_check() {
    label="$1"
    shift
    printf '\n[%s] %s\n' "$label" "$*"
    "$@"
    code=$?
    if [ "$code" -eq 0 ]; then
        printf '[%s] PASS\n' "$label"
    else
        printf '[%s] FAIL exit=%s\n' "$label" "$code"
        status=1
    fi
}

printf '== user-management quality gate ==\n'

if bash .agents/skills/project-quality/scripts/preflight_check.sh; then
    printf '\n[preflight] PASS\n'
else
    printf '\n[preflight] FAIL: environment is not ready for quality checks\n'
    exit 1
fi

PYTHON_BIN="$(pick_python)"

printf '\n[python] using %s\n' "$PYTHON_BIN"

if "$PYTHON_BIN" -c "import ruff" >/dev/null 2>&1; then
    run_check "ruff" "$PYTHON_BIN" -m ruff check app tests
else
    printf '\n[ruff] SKIP: ruff is not installed in %s\n' "$PYTHON_BIN"
fi

if "$PYTHON_BIN" -c "import mypy" >/dev/null 2>&1; then
    run_check "mypy" "$PYTHON_BIN" -m mypy app
else
    printf '\n[mypy] SKIP: mypy is not installed in %s\n' "$PYTHON_BIN"
fi

run_check "pytest" "$PYTHON_BIN" -m pytest -q

printf '\n== quality gate result: '
if [ "$status" -eq 0 ]; then
    printf 'PASS ==\n'
else
    printf 'FAIL ==\n'
fi

exit "$status"
