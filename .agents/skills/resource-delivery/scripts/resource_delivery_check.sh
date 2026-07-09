#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT_DIR" || exit 1

status=0
module_name="${1:-}"

print_usage() {
    printf 'Usage: bash .agents/skills/resource-delivery/scripts/resource_delivery_check.sh <module_name>\n'
    printf 'Example: bash .agents/skills/resource-delivery/scripts/resource_delivery_check.sh role\n'
}

pass() {
    printf '[PASS] %s\n' "$1"
}

fail() {
    printf '[FAIL] %s\n' "$1"
    status=1
}

warn() {
    printf '[WARN] %s\n' "$1"
}

require_file() {
    path="$1"
    if [ -f "$path" ]; then
        pass "file exists: $path"
    else
        fail "missing file: $path"
    fi
}

require_pattern() {
    path="$1"
    pattern="$2"
    description="$3"
    if [ ! -f "$path" ]; then
        fail "cannot inspect missing file: $path"
        return
    fi
    if grep -Eq "$pattern" "$path"; then
        pass "$description"
    else
        fail "$description"
    fi
}

snake_to_pascal() {
    printf '%s\n' "$1" | awk -F_ '{
        out="";
        for (i = 1; i <= NF; i++) {
            out = out toupper(substr($i,1,1)) substr($i,2)
        }
        print out
    }'
}

if [ -z "$module_name" ]; then
    print_usage
    exit 2
fi

case "$module_name" in
    *[!a-z0-9_]* | "" | [0-9]*)
        fail "module_name must be lower snake_case and not start with a number: $module_name"
        exit "$status"
        ;;
esac

class_prefix="$(snake_to_pascal "$module_name")"
sql_file="sql/t_${module_name}.sql"
model_file="app/models/${module_name}.py"
schema_file="app/schemas/${module_name}.py"
crud_file="app/crud/${module_name}.py"
api_file="app/api/${module_name}.py"

printf '== resource delivery check: %s ==\n' "$module_name"

require_file "$sql_file"
require_file "$model_file"
require_file "$schema_file"
require_file "$crud_file"
require_file "$api_file"

if compgen -G "tests/test_${module_name}*.py" >/dev/null; then
    pass "tests exist: tests/test_${module_name}*.py"
else
    fail "missing tests: tests/test_${module_name}*.py"
fi

require_pattern "$sql_file" '`id`[[:space:]]+BIGINT UNSIGNED[[:space:]]+NOT NULL[[:space:]]+AUTO_INCREMENT' "SQL defines BIGINT UNSIGNED id"
require_pattern "$sql_file" '`is_deleted`[[:space:]]+TINYINT UNSIGNED NOT NULL DEFAULT 0' "SQL defines standard is_deleted"
require_pattern "$sql_file" '`gmt_create`[[:space:]]+DATETIME[[:space:]]+NOT NULL DEFAULT CURRENT_TIMESTAMP' "SQL defines gmt_create"
require_pattern "$sql_file" '`gmt_modified`[[:space:]]+DATETIME[[:space:]]+NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP' "SQL defines gmt_modified"
require_pattern "$sql_file" 'COMMENT=' "SQL table has table comment"

require_pattern "$model_file" '__tablename__[[:space:]]*=[[:space:]]*"t_'"${module_name}"'"' "Model maps t_${module_name}"
require_pattern "$model_file" 'is_deleted' "Model includes is_deleted"
require_pattern "$model_file" 'gmt_create' "Model includes gmt_create"
require_pattern "$model_file" 'gmt_modified' "Model includes gmt_modified"

require_pattern "$schema_file" "class ${class_prefix}Create" "Schema defines ${class_prefix}Create"
require_pattern "$schema_file" "class ${class_prefix}Update" "Schema defines ${class_prefix}Update"
require_pattern "$schema_file" "class ${class_prefix}Out" "Schema defines ${class_prefix}Out"
require_pattern "$schema_file" "class ${class_prefix}Page" "Schema defines ${class_prefix}Page"
require_pattern "$schema_file" 'from_attributes[[:space:]]*=[[:space:]]*True' "Schema Out supports ORM validation"

require_pattern "$crud_file" 'BusinessException' "CRUD raises BusinessException"
require_pattern "$crud_file" 'CODE_NOT_FOUND[[:space:]]*=[[:space:]]*40400' "CRUD defines not-found error code"
require_pattern "$crud_file" 'is_deleted[[:space:]]*==[[:space:]]*0' "CRUD filters active rows"
require_pattern "$crud_file" 'is_deleted[[:space:]]*=[[:space:]]*1' "CRUD performs logical delete"

require_pattern "$api_file" 'APIRouter\(prefix="/api/v1/' "API uses /api/v1 prefix"
require_pattern "$api_file" 'ApiResponse' "API returns ApiResponse"
require_pattern "$api_file" 'Path\(\.\.\.,[[:space:]]*ge=1' "API constrains path id"
require_pattern "$api_file" 'Query\(1,[[:space:]]*ge=1' "API constrains page"
require_pattern "$api_file" 'Query\(10,[[:space:]]*ge=1,[[:space:]]*le=100' "API constrains page_size"

if grep -Eq "from app.api.${module_name} import router as .*router" app/main.py \
    && grep -Eq "include_router\\(.*${module_name}.*router\\)" app/main.py; then
    pass "main.py registers ${module_name} router"
else
    fail "main.py does not appear to register ${module_name} router"
fi

if grep -Eq "t_${module_name}|/api/v1/${module_name}s" docs/API.md; then
    pass "docs/API.md appears to mention resource"
else
    warn "docs/API.md resource mention not detected; verify docs manually"
fi

printf '== resource delivery result: '
if [ "$status" -eq 0 ]; then
    printf 'PASS ==\n'
else
    printf 'FAIL ==\n'
fi

exit "$status"
