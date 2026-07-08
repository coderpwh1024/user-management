---
name: scaffold-resource
description: 当需要在本项目新增一个资源/数据表（t_xxx）并按 CLAUDE.md 第九章交付清单一次产出 sql/model/schema/crud/api/test/API.md 全套文件时使用。触发词：新增资源、新增表、scaffold、脚手架、生成 CRUD、新建模块、按交付清单生成。
---

# scaffold-resource —— 资源脚手架（FastAPI 分层 CRUD）

## Overview

本项目（用户管理服务）采用 **FastAPI + Pydantic v2 + SQLAlchemy 2.0 + MySQL** 严格分层，
每个资源都要按 `CLAUDE.md` 第九章"交付清单"产出 7 类文件。本技能把这一过程标准化：
**以现有 `t_user` 全套文件为风格范本**，逐文件对照生成新资源，并消解项目中的命名不一致。

核心原则：**不重复抄规范，而是读现有代码当范本**；规范升级时本技能不过时。

## 何时使用

- 用户要"新增一个资源 / 一张表 / 一个模块"，例如"新增角色 t_role，字段 role_code(唯一)、role_name、status"。
- 用户明确说"按交付清单生成"、"生成全套 CRUD"、"scaffold / 脚手架"。
- **不适用**：只改一个已有接口（改字段校验、加一个查询条件）→ 直接改对应文件即可，无需走全流程。

## 关键决策（最容易做错，务必照此执行）

> **新表命名走第四章新规范，绝不照抄旧表 `t_user` 的命名。**

`t_user` 是**结构/风格**范本，但它的字段命名是历史遗留、与规范不一致。新资源必须：

| 用途 | 旧表 t_user（勿抄） | 新表必须用（第四章） |
| ---- | ------------------ | -------------------- |
| 逻辑删除 | `is_delete` | **`is_deleted`** TINYINT UNSIGNED |
| 创建时间 | `create_date` | **`gmt_create`** DATETIME |
| 更新时间 | `update_time` | **`gmt_modified`** DATETIME ON UPDATE |

→ 因此新资源的 `model` / `crud` / `schema(Out)` 里，所有过滤、字段名都用 `is_deleted` / `gmt_create` / `gmt_modified`，
而不是 `t_user` 里的旧名。`crud` 中过滤条件写 `Xxx.is_deleted == 0`。

## 执行流程

### 第 0 步：先读范本（必做，不要跳过）

并行读取以下文件，作为逐文件生成的范本与风格基准：
`sql/t_user.sql`、`app/models/user.py`、`app/schemas/user.py`、`app/crud/user.py`、
`app/api/user.py`、`app/main.py`、`docs/API.md`、`tests/test_validators.py`、`app/core/response.py`、
`app/core/exceptions.py`、`app/utils/validators.py`。

### 第 1 步：确认输入

向用户确认（缺啥问啥，不要自行臆造业务字段）：
- 资源中文名、表名 `t_xxx`（单数、`t_` 前缀）。
- 字段清单：每个字段的 名 / 类型 / 是否必填 / 是否唯一 / 是否建索引 / 枚举注释。
- 需要哪些接口（默认：创建 / 详情 / 分页 / 更新 / 逻辑删除 全套）。
- 分页的过滤条件（哪些字段模糊匹配、哪些精确匹配 / 枚举过滤）。

### 第 2 步：按交付清单逐文件生成

| # | 文件 | 对照范本 | 要点 |
| - | ---- | -------- | ---- |
| 1 | `sql/t_xxx.sql` | `sql/t_user.sql` | 三必备字段(`id`/`gmt_create`/`gmt_modified`)+`is_deleted`；唯一键 `uk_字段`、普通索引 `idx_字段`；每字段 `COMMENT`，枚举值列全；`utf8mb4` / `utf8mb4_0900_ai_ci` / `InnoDB`；附少量示例 `INSERT`。 |
| 2 | `app/models/xxx.py` | `app/models/user.py` | `Mapped[...]` / `mapped_column`，字段带 `comment=`；时间用 `gmt_create`/`gmt_modified`（`server_default=func.now()`，更新时间加 `onupdate=func.now()`）；逻辑删除 `is_deleted`。**主键 id 用 `BigInteger().with_variant(Integer, "sqlite")`**——否则内存 SQLite 集成测试下 BIGINT 主键不自增（SQLite 仅 INTEGER 主键自增），MySQL 仍为 BIGINT。 |
| 3 | `app/schemas/xxx.py` | `app/schemas/user.py` | 四件套 `XxxCreate/Update/Out/Page`；`Update` 全字段 `Optional`；`Field(min_length/max_length/ge/le)`；唯一/格式字段用 `@field_validator` 复用 `app/utils/`（无现成校验器则在 `utils/` 新增纯函数并补单测）；`Out` 用 `model_config = ConfigDict(from_attributes=True)`，含 `gmt_create`/`gmt_modified`。 |
| 4 | `app/crud/xxx.py` | `app/crud/user.py` | 顶部定义错误码常量 `CODE_NOT_FOUND=40400`、唯一冲突 `CODE_XXX_EXISTS=40901`（按五位码规律）；**所有查询追加 `Xxx.is_deleted == 0`**；唯一性校验、不存在校验抛 `BusinessException`；`update` 用 `model_dump(exclude_unset=True, exclude_none=True)`；`delete` 置 `is_deleted=1`（禁物理删除）；关键分支打 `logger`，敏感字段脱敏。 |
| 5 | `app/api/xxx.py` | `app/api/user.py` | `APIRouter(prefix="/api/v1/<资源复数>")`；五个路由用 `response_model=ApiResponse[...]`，返回 `ApiResponse.ok(...)`；路径参数 `Path(..., ge=1)`，分页 `Query(page≥1, page_size∈[1,100])`；**只接收参数+调 crud+包响应，不写业务逻辑**。 |
| 5b | `app/main.py` | —— | 在 `create_app()` 中 `import` 并 `app.include_router(xxx_router)`，仿照 `user_router` 注册。 |
| 6 | `tests/test_xxx*.py` | `tests/test_validators.py` | 校验器用 `@pytest.mark.parametrize` 覆盖正例/边界/非法；crud/api 推荐内存 SQLite 集成测试，覆盖逻辑删除、唯一冲突分支。 |
| 7 | `docs/API.md` | `docs/API.md` | 追加该资源接口段落：路径、方法、请求/响应示例、字段校验规则、错误码、cURL，保持现有文档风格。 |

### 第 3 步：自检 + 验证（收尾必做）

逐条核对 `CLAUDE.md` 末尾自检清单：
- 分层是否倒置？查询是否都过滤 `is_deleted`？响应是否 `ApiResponse`？
- 表是否含三必备字段 + `is_deleted`？索引是否 `uk_/idx_` 命名？字段是否带注释？
- 命名是否四件套？`Update` 是否全可选？错误码是否五位码常量？

然后运行并把结果报告给用户：
```bash
ruff check app/ tests/
python -m pytest -q
```

## 常见错误（来自项目实际）

| 错误 | 正确做法 |
| ---- | -------- |
| 新表照抄 `t_user` 用 `is_delete`/`create_date`/`update_time` | 新表用 `is_deleted`/`gmt_create`/`gmt_modified`（见上方决策表） |
| `crud` 某个查询漏了 `is_deleted == 0`（最常漏 get、唯一校验） | 每个 `select` 都带逻辑删除过滤 |
| 在 `api` 层写业务逻辑或 SQL | 业务逻辑全在 `crud`，api 只编排 |
| 生成了 `api` 却忘记在 `main.py` 注册路由 | 第 5b 步必做 |
| 业务异常返回 HTTP 4xx/5xx | 业务异常 HTTP 仍 200，错误体现在 `code`；仅未捕获系统异常返 500 |
| 错误码硬编码在路由里 | 错误码常量定义在 `crud` 层 |
| 日志打印完整身份证/手机号 | 敏感字段脱敏（如身份证留前 6 后 4） |
| 测试断言"软删除后可重用唯一键" | DB 唯一索引（`uk_xxx`）+ 逻辑删除是固有张力：软删除行物理仍在，唯一键被占用，删除后**不可直接重用**；crud 的唯一预检只过滤 `is_deleted==0`，撞到软删除行会漏判并由 DB 抛 `IntegrityError`。测试只验证过滤语义，勿断言重用。 |
| 主键用 `BigInteger` 直接跑 SQLite 测试 | 用 `BigInteger().with_variant(Integer, "sqlite")`，否则主键不自增 |

## 联网核对（可选）

如对锁定版本（FastAPI 0.115 / Pydantic 2.10 / SQLAlchemy 2.0）的某处写法不确定，
用 context7（`resolve-library-id` → `query-docs`）核对一次即可。**默认以现有 `t_user` 代码为准**——它已是版本正确的范本。
