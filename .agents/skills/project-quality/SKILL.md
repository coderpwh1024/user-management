---
name: project-quality
description: Run the user-management quality gate after code changes. Use when the user asks for quality checks, test checks, lint/type/test validation, or before finishing a change.
---

# project-quality - 项目质量检查工作流

## Overview

本技能用于本项目的固定质量门禁。它把当前仓库的质量检查顺序标准化，避免每次改动后遗漏测试、静态检查或验证结果说明。

## When to Use

- 用户要求“质量检查”“跑测试”“验证一下”“检查这次改动”。
- 完成任意 `app/`、`tests/`、`sql/`、`docs/API.md` 相关改动后。
- 新资源脚手架或代码审查之后，需要确认项目仍可运行。

## Environment Setup

首次运行或开发依赖变更后安装锁定的质量工具：

```bash
python -m pip install -r requirements-dev.txt
```

## Required Checks

优先运行仓库内脚本：

```bash
bash .agents/skills/project-quality/scripts/quality_check.sh
```

脚本会按顺序执行：

1. `bash .agents/skills/project-quality/scripts/preflight_check.sh`。
2. `ruff check app tests`（如本地安装了 ruff）。
3. `mypy app`（如本地安装了 mypy）。
4. 使用脚本选中的 Python 解释器运行 `-m pytest -q`。

如果 `ruff` 或 `mypy` 未安装，脚本只标记为跳过，不阻塞测试执行；`pytest` 失败必须视为质量门禁失败。
如需指定解释器，可设置 `QUALITY_PYTHON=/path/to/python`。

## Reporting

最终回复用户时必须说明：

- 实际运行的命令。
- 每个检查的结果：通过、失败或跳过。
- 如果失败，列出首个关键错误和建议下一步。

## Project-Specific Attention

检查结果之外，还要快速确认：

- 新增/修改 CRUD 查询是否过滤 `is_deleted == 0`。
- API 层是否只做参数接收、调用 CRUD/Service、封装 `ApiResponse`。
- 业务异常是否通过 `BusinessException`，未把 HTTP 响应混入 CRUD。
- 敏感信息日志是否脱敏。
- 文档和测试是否与接口变更同步。
