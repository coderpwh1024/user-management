---
name: resource-delivery
description: End-to-end workflow for delivering a new user-management resource. Chains scaffold-resource, project-review, and project-quality in order.
---

# resource-delivery - 新资源端到端交付工作流

## Overview

本技能是新资源交付的总入口，用于把三个独立工作流串起来：

1. `preflight`：识别环境风险，避免把环境问题误判为代码问题。
2. `scaffold-resource`：生成新资源全套文件。
3. `resource_delivery_check`：做交付物确定性检查。
4. `project-review`：审查生成差异。
5. `project-quality`：运行质量门禁。

## When to Use

- 用户说“新增资源并完整交付”“从脚手架到检查都做完”“把新资源 workflow 串起来”。
- 用户提供了资源中文名、表名、字段、接口、分页过滤条件，并希望一次完成。

## Execution Order

### Step 0: Preflight

先运行：

```bash
bash .agents/skills/project-quality/scripts/preflight_check.sh
```

如果失败，记录环境限制；除非用户明确要求继续，否则不要开始大量生成代码。

### Step 1: Scaffold

先按 `.agents/skills/scaffold-resource/SKILL.md` 执行。

如果用户缺少必要信息，先问清楚：

- 资源中文名、表名。
- 字段名、类型、是否必填、是否唯一、索引、枚举注释。
- 接口范围，默认创建 / 详情 / 分页 / 更新 / 逻辑删除。
- 分页过滤条件。

产出必须覆盖：

- `sql/t_xxx.sql`
- `app/models/xxx.py`
- `app/schemas/xxx.py`
- `app/crud/xxx.py`
- `app/api/xxx.py`
- `app/main.py`
- `tests/test_xxx*.py`
- `docs/API.md`

### Step 2: Deterministic Delivery Check

生成后运行：

```bash
bash .agents/skills/resource-delivery/scripts/resource_delivery_check.sh <module_name>
```

如失败，先修复缺失文件、路由注册、SQL 标准字段、逻辑删除、分页参数等确定性问题。

### Step 3: Review

生成后立即按 `.agents/skills/project-review/SKILL.md` 审查当前差异。

必须重点检查：

- API / CRUD / Model / Schema 分层。
- 所有查询是否过滤 `is_deleted == 0`。
- SQL 是否符合新表 `gmt_create/gmt_modified/is_deleted` 规约。
- API 是否统一返回 `ApiResponse`。
- 错误码、日志脱敏、测试、文档是否完整。

如发现阻塞问题，先修复，再重新审查相关差异。

### Step 4: Quality Gate

最后按 `.agents/skills/project-quality/SKILL.md` 运行：

```bash
bash .agents/skills/project-quality/scripts/quality_check.sh
```

如果当前环境无法运行测试，必须说明真实原因，并给出可复现的命令。

## Definition of Done

同时满足以下条件才算完成：

- 交付清单文件全部存在。
- `resource_delivery_check.sh <module_name>` 通过。
- 代码审查无阻塞 Findings。
- `quality_check.sh` 通过；如因环境失败，必须明确记录并给出用户可复现命令。
- `docs/API.md` 已更新。
- 最终报告按 `.agents/skills/resource-delivery/templates/resource-delivery-report.md` 汇总。

## Failure Policy

- 环境失败：先停止并报告，除非用户明确允许继续。
- 确定性检查失败：修复后重跑该检查。
- Review 阻塞问题：修复后重新 review。
- 测试失败：定位首个关键失败，优先修复最小范围问题。
- 业务信息不足：只问必要问题，不自行臆造字段或规则。

## Final Report

最终回复必须包含：

- 生成/修改的文件。
- 代码审查结果，按 Findings 优先。
- 确定性检查结果。
- 质量门禁结果：ruff / mypy / pytest 通过、失败或跳过。
- 未完成项或环境限制。
