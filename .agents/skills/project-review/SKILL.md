---
name: project-review
description: Review user-management changes for backend correctness, layering, database rules, API contracts, security, and missing tests. Use when the user asks for code review, PR review, or before landing changes.
---

# project-review - 项目代码审查工作流

## Overview

本技能用于本项目的代码审查。默认采取缺陷优先的 review 姿态：先列风险、bug、回归和缺失测试，再给总结。

## When to Use

- 用户要求“代码审查”“review”“PR 检查”“落库前看一下”。
- 新资源脚手架完成后。
- 修改 `api / crud / models / schemas / services / sql / tests / docs` 任一层后。

## Inputs to Inspect

优先查看当前差异：

```bash
git diff -- app tests sql docs .codex .agents
```

如需要上下文，再读取相关文件：

- `app/main.py`
- 受影响的 `app/api/*.py`
- 受影响的 `app/crud/*.py`
- 受影响的 `app/models/*.py`
- 受影响的 `app/schemas/*.py`
- 受影响的 `sql/t_*.sql`
- 受影响的 `tests/test_*.py`
- `docs/API.md`

## Review Checklist

按严重程度检查：

1. 分层边界：`api -> crud -> models/schemas`，禁止 API 写 SQL，禁止 CRUD 返回 HTTP 响应。
2. 逻辑删除：所有查询、唯一性预检、详情、分页都过滤 `is_deleted == 0`。
3. 数据库规约：新表含 `id/gmt_create/gmt_modified/is_deleted`，字段注释完整，索引命名 `uk_/idx_`。
4. API 合约：统一 `/api/v1/<resources>`，返回 `ApiResponse`，业务异常 code 与 HTTP 解耦。
5. 校验：Schema 使用 Pydantic v2，字段边界和 `field_validator` 调用纯函数。
6. 安全：日志不输出完整身份证、密码、密钥、连接串；配置不硬编码。
7. 测试：覆盖校验器、逻辑删除、唯一冲突、分页过滤、后台任务关键分支。
8. 文档：`docs/API.md` 是否覆盖新增/变更接口、错误码、字段规则和 cURL。

## Output Format

有问题时：

```text
Findings
- [Severity] path:line - 问题说明。说明真实风险和建议修复方向。

Open Questions
- ...

Summary
- ...
```

无问题时：

```text
未发现阻塞问题。
验证缺口：...
```

## Verification

审查后建议运行：

```bash
bash .agents/skills/project-quality/scripts/quality_check.sh
```
