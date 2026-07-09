# Codex 工作流

本文记录本项目优先落地的 Codex 工作流。

## 0. 新资源端到端交付

入口：`.agents/skills/resource-delivery/SKILL.md`

脚本与模板沉淀在 skill 目录：

- `.agents/skills/project-quality/scripts/preflight_check.sh`
- `.agents/skills/resource-delivery/scripts/resource_delivery_check.sh`
- `.agents/skills/project-quality/scripts/quality_check.sh`
- `.agents/skills/resource-delivery/templates/resource-delivery-report.md`

用途：把环境预检、新资源脚手架、确定性检查、代码审查、质量检查串联起来，一次完成资源交付。

执行顺序：

1. `bash .agents/skills/project-quality/scripts/preflight_check.sh`
2. `$scaffold-resource`
3. `bash .agents/skills/resource-delivery/scripts/resource_delivery_check.sh <module_name>`
4. `$project-review`
5. `$project-quality`

完成标准：

- 交付清单文件全部存在。
- 确定性交付检查通过。
- 代码审查无阻塞问题。
- 质量门禁通过，或明确记录环境限制与复现命令。
- 最终报告参考 `.agents/skills/resource-delivery/templates/resource-delivery-report.md`。

## 1. 新资源脚手架

入口：`.agents/skills/scaffold-resource/SKILL.md`

用途：新增 `t_xxx` 资源时，按交付清单一次生成 `sql/model/schema/crud/api/test/docs`。

## 2. 质量检查

入口：`.agents/skills/project-quality/SKILL.md`

脚本：`.agents/skills/project-quality/scripts/quality_check.sh`

预检脚本：`.agents/skills/project-quality/scripts/preflight_check.sh`

运行：

```bash
bash .agents/skills/project-quality/scripts/quality_check.sh
```

检查顺序：

1. 环境预检。
2. `ruff check app tests`，未安装则跳过。
3. `mypy app`，未安装则跳过。
4. 使用脚本选中的 Python 解释器运行 `-m pytest -q`。

可通过 `QUALITY_PYTHON=/path/to/python` 指定解释器。

## 3. 代码审查

入口：`.agents/skills/project-review/SKILL.md`

审查重点：

- 分层边界。
- 逻辑删除过滤。
- SQL 建表规约。
- `ApiResponse` 和 `BusinessException`。
- 日志脱敏。
- 测试与文档同步。

## 官方依据

- Codex Workflows: https://developers.openai.com/codex/workflows
- Codex GitHub Action: https://developers.openai.com/codex/github-action
- Codex Hooks: https://developers.openai.com/codex/hooks
