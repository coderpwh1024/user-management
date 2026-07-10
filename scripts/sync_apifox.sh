#!/usr/bin/env bash
# =============================================================
# 将 docs/openapi.yaml 同步到 Apifox 远程项目文档
# 凭证读取自 .apifox/settings.json(不入库),一次 HTTP 请求完成同步
# 用法: bash scripts/sync_apifox.sh
# =============================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETTINGS_FILE="$PROJECT_ROOT/.apifox/settings.json"
SPEC_FILE="$PROJECT_ROOT/docs/openapi.yaml"

if [[ ! -f "$SETTINGS_FILE" ]]; then
    echo "错误: 未找到 $SETTINGS_FILE,请先配置 projectId 与 accessToken" >&2
    exit 1
fi
if [[ ! -f "$SPEC_FILE" ]]; then
    echo "错误: 未找到 OpenAPI 文档 $SPEC_FILE" >&2
    exit 1
fi

PROJECT_ID="$(jq -r '.projectId' "$SETTINGS_FILE")"
ACCESS_TOKEN="$(jq -r '.accessToken' "$SETTINGS_FILE")"

# endpointOverwriteBehavior=OVERWRITE_EXISTING: 同名接口覆盖更新,保证远程与本地一致
BODY="$(jq -n --rawfile spec "$SPEC_FILE" '{
    input: $spec,
    options: {
        endpointOverwriteBehavior: "OVERWRITE_EXISTING",
        endpointCaseOverwriteBehavior: "OVERWRITE_EXISTING",
        updateFolderOfChangedEndpoint: false
    }
}')"

echo "正在同步 $SPEC_FILE -> Apifox 项目 $PROJECT_ID ..."
HTTP_CODE="$(curl -sS -o /tmp/apifox_sync_resp.json -w '%{http_code}' \
    -X POST "https://api.apifox.com/v1/projects/${PROJECT_ID}/import-openapi?locale=zh-CN" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "X-Apifox-Api-Version: 2024-03-28" \
    -H "Content-Type: application/json" \
    --data-binary "$BODY")"

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "同步失败 (HTTP $HTTP_CODE):" >&2
    cat /tmp/apifox_sync_resp.json >&2
    exit 1
fi

echo "同步成功,变更统计:"
jq '.data.counters' /tmp/apifox_sync_resp.json
