# 用户管理服务（User Management）

基于 **FastAPI + Pydantic v2 + SQLAlchemy 2.0 + MySQL** 实现的用户增删改查服务。
采用分层架构，包含字段校验、统一响应、全局异常处理、逻辑删除与日志记录。

## 一、技术栈

| 组件 | 版本 | 说明 |
| ---- | ---- | ---- |
| Python | 3.10+ | 运行环境 |
| FastAPI | 0.115 | Web 框架 |
| Pydantic | 2.x | 数据校验 / 序列化 |
| SQLAlchemy | 2.0 | ORM 持久层 |
| PyMySQL | 1.x | MySQL 驱动 |
| MySQL | 8.0+ | 数据库 |

## 二、项目结构

```
user-management/
├── app/
│   ├── main.py              # 应用入口（FastAPI 实例）
│   ├── core/                # 基础设施
│   │   ├── config.py        # 配置（pydantic-settings）
│   │   ├── logger.py        # 日志
│   │   ├── response.py      # 统一响应封装
│   │   └── exceptions.py    # 业务异常 + 全局异常处理
│   ├── db/
│   │   └── session.py       # 引擎 / 会话 / get_db 依赖
│   ├── models/
│   │   └── user.py          # User ORM 模型（t_user）
│   ├── schemas/
│   │   └── user.py          # Pydantic 请求 / 响应模型
│   ├── crud/
│   │   └── user.py          # 持久层 CRUD
│   ├── api/
│   │   └── user.py          # 路由层
│   └── utils/
│       └── validators.py    # 手机号 / 身份证校验
├── sql/
│   └── t_user.sql           # 数据库初始化脚本
├── docs/
│   └── API.md               # 接口文档
├── tests/
│   └── test_validators.py   # 单元测试
├── requirements.txt
└── .env.example
```

## 三、快速开始

### 1. 初始化数据库

```bash
mysql -u root -p < sql/t_user.sql
```

### 2. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 按需修改 .env 中的数据库连接信息
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问：

- Swagger UI： <http://localhost:8000/docs>
- ReDoc： <http://localhost:8000/redoc>
- 健康检查： <http://localhost:8000/health>

### 5. 运行测试

```bash
pip install pytest
pytest -v
```

## 四、接口一览

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/users` | 创建用户 |
| GET | `/api/v1/users/{id}` | 查询用户详情 |
| GET | `/api/v1/users` | 分页查询用户 |
| PUT | `/api/v1/users/{id}` | 更新用户 |
| DELETE | `/api/v1/users/{id}` | 逻辑删除用户 |

详细请求 / 响应示例见 [docs/API.md](docs/API.md)。

## 五、设计要点
- **分层架构**：`api` → `crud` → `models`，schema 与 model 分离，职责清晰。
- **字段校验**：手机号正则校验；身份证号正则 + GB11643 校验位双重校验。
- **逻辑删除**：所有查询自动过滤 `is_delete=1`，删除仅置标志位。
- **统一响应**：`{code, message, data}`，配合全局异常处理保证返回结构一致。
- **唯一约束**：身份证号库内唯一，创建 / 更新均做唯一性校验。
- **日志规范**：关键接口与业务分支均打印日志，便于排查。
- **代码规范**：模块 / 函数均带 docstring，命名遵循 PEP8 与大厂 Python 规范。

##  七