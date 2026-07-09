# 新资源交付报告

## 输入

- 资源中文名：
- 表名：
- 模块名：
- 字段摘要：
- 接口范围：
- 分页过滤：

## 生成 / 修改文件

- `sql/t_xxx.sql`
- `app/models/xxx.py`
- `app/schemas/xxx.py`
- `app/crud/xxx.py`
- `app/api/xxx.py`
- `app/main.py`
- `tests/test_xxx*.py`
- `docs/API.md`

## 代码审查

Findings:

- 未发现 / 待填写

Open Questions:

- 未发现 / 待填写

## 确定性检查

命令：

```bash
bash .agents/skills/resource-delivery/scripts/resource_delivery_check.sh xxx
```

结果：

- PASS / FAIL / 未运行

## 质量门禁

命令：

```bash
bash .agents/skills/project-quality/scripts/quality_check.sh
```

结果：

- preflight：
- ruff：
- mypy：
- pytest：

## 已知未知

- 当前环境限制：
- 依赖/配置假设：
- 需要人工确认的业务规则：

## 未知的未知防护

- 是否有回归测试覆盖关键路径：
- 是否有文档和 cURL 示例：
- 是否避免敏感信息日志：
- 是否保留最小变更范围：

## 结论

- 可交付 / 暂不可交付：
- 阻塞项：
- 后续建议：
