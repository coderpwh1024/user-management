#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT_DIR" || exit 1

status=0

print_result() {
    label="$1"
    result="$2"
    detail="$3"
    printf '[%s] %s: %s\n' "$label" "$result" "$detail"
}

mark_fail() {
    status=1
}

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

printf '== user-management preflight ==\n'

if [ -f "AGENTS.md" ] && [ -d "app" ] && [ -d "tests" ]; then
    print_result "workspace" "PASS" "$ROOT_DIR"
else
    print_result "workspace" "FAIL" "must run from repository root"
    mark_fail
fi

PYTHON_BIN="$(pick_python || true)"
if [ -z "${PYTHON_BIN:-}" ]; then
    print_result "python" "FAIL" "no usable Python 3.10+ interpreter found"
    mark_fail
else
    PYTHON_VERSION="$("$PYTHON_BIN" - <<'PY'
import sys
print(".".join(str(part) for part in sys.version_info[:3]))
PY
)"
    if "$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
    then
        print_result "python" "PASS" "$PYTHON_BIN ($PYTHON_VERSION)"
    else
        print_result "python" "FAIL" "$PYTHON_BIN ($PYTHON_VERSION) is below project requirement 3.10+"
        mark_fail
    fi
fi

if [ -n "${PYTHON_BIN:-}" ]; then
    for module in fastapi pydantic sqlalchemy pytest; do
        if "$PYTHON_BIN" -c "import ${module}" >/dev/null 2>&1; then
            print_result "python-module" "PASS" "$module"
        else
            print_result "python-module" "FAIL" "$module is not importable by $PYTHON_BIN"
            mark_fail
        fi
    done
fi

if [ -n "${PYTHON_BIN:-}" ] && "$PYTHON_BIN" -c "import ruff" >/dev/null 2>&1; then
    print_result "tool" "PASS" "ruff is installed in $PYTHON_BIN"
else
    print_result "tool" "WARN" "ruff is not installed in the selected Python; lint check will be skipped"
fi

if [ -n "${PYTHON_BIN:-}" ] && "$PYTHON_BIN" -c "import mypy" >/dev/null 2>&1; then
    print_result "tool" "PASS" "mypy is installed in $PYTHON_BIN"
else
    print_result "tool" "WARN" "mypy is not installed in the selected Python; type check will be skipped"
fi

if GIT_CONFIG_GLOBAL=/dev/null XDG_CONFIG_HOME=/private/tmp git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    print_result "git" "PASS" "repository detected"
else
    print_result "git" "WARN" "git metadata unavailable; review diff commands may be limited"
fi

printf '== preflight result: '
if [ "$status" -eq 0 ]; then
    printf 'PASS ==\n'
else
    printf 'FAIL ==\n'
fi

exit "$status"
