# 用户管理接口文档

- **Base URL**：`http://localhost:8000`
- **统一前缀**：`/api/v1/users`
- **数据格式**：`application/json`

## 一、统一响应结构

所有接口返回如下结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| code | int | 业务状态码，`0` 表示成功，非 0 表示业务错误 |
| message | string | 提示信息 |
| data | object/null | 业务数据 |

### 业务错误码

| code | 说明 |
| ---- | ---- |
| 0 | 成功 |
| 40400 | 用户不存在 |
| 40901 | 身份证号已存在 |
| 42200 | 参数校验失败 |
| 50000 | 系统内部错误 |

## 二、字段校验规则

| 字段 | 规则 |
| ---- | ---- |
| name | 必填，长度 1–64 |
| age | 选填，0–150 |
| phone | 必填，匹配 `^1[3-9]\d{9}$` |
| id_card | 必填，18 位，正则 + GB11643 校验位校验，库内唯一 |
| gender | 0:未知 1:男 2:女，默认 0 |

---

## 三、接口明细

### 1. 创建用户

`POST /api/v1/users`

**请求体**

```json
{
  "name": "张三",
  "age": 28,
  "phone": "13800138000",
  "id_card": "110101199003077352",
  "gender": 1,
  "create_by": "admin"
}
```

**响应**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "name": "张三",
    "age": 28,
    "phone": "13800138000",
    "id_card": "110101199003077352",
    "gender": 1,
    "create_by": "admin",
    "update_by": null,
    "create_date": "2026-06-01T10:00:00",
    "update_time": "2026-06-01T10:00:00"
  }
}
```

**cURL**

```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"name":"张三","age":28,"phone":"13800138000","id_card":"110101199003077352","gender":1,"create_by":"admin"}'
```

---

### 2. 查询用户详情

`GET /api/v1/users/{id}`

| 参数 | 位置 | 类型 | 说明 |
| ---- | ---- | ---- | ---- |
| id | path | int | 用户 ID（≥1） |

**响应**：同创建用户的 `data` 结构。用户不存在时返回 `code=40400`。

```bash
curl http://localhost:8000/api/v1/users/1
```

---

### 3. 分页查询用户

`GET /api/v1/users`

| 参数 | 位置 | 类型 | 默认 | 说明 |
| ---- | ---- | ---- | ---- | ---- |
| page | query | int | 1 | 页码（≥1） |
| page_size | query | int | 10 | 每页条数（1–100） |
| name | query | string | - | 姓名，模糊匹配 |
| phone | query | string | - | 手机号，精确匹配 |

**响应**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 2,
    "page": 1,
    "page_size": 10,
    "items": [
      {
        "id": 2,
        "name": "李四",
        "age": 32,
        "phone": "13900139000",
        "id_card": "310101198805054323",
        "gender": 2,
        "create_by": "system",
        "update_by": null,
        "create_date": "2026-06-01T10:00:00",
        "update_time": "2026-06-01T10:00:00"
      }
    ]
  }
}
```

```bash
curl "http://localhost:8000/api/v1/users?page=1&page_size=10&name=李"
```

---

### 4. 更新用户

`PUT /api/v1/users/{id}`

仅更新请求体中传入的字段（局部更新）。

**请求体**

```json
{
  "age": 30,
  "phone": "13700137000",
  "update_by": "admin"
}
```

**响应**：返回更新后的完整用户对象。用户不存在返回 `40400`；身份证号冲突返回 `40901`。

```bash
curl -X PUT http://localhost:8000/api/v1/users/1 \
  -H "Content-Type: application/json" \
  -d '{"age":30,"phone":"13700137000","update_by":"admin"}'
```

---

### 5. 删除用户（逻辑删除）

`DELETE /api/v1/users/{id}`

将 `is_delete` 置为 1，不做物理删除。

**响应**

```json
{
  "code": 0,
  "message": "删除成功",
  "data": null
}
```

```bash
curl -X DELETE http://localhost:8000/api/v1/users/1
```

---

## 四、角色管理接口

- **统一前缀**：`/api/v1/roles`

### 业务错误码

| code | 说明 |
| ---- | ---- |
| 0 | 成功 |
| 40400 | 角色不存在 |
| 40901 | 角色编码已存在 |
| 42200 | 参数校验失败 |
| 50000 | 系统内部错误 |

### 字段校验规则

| 字段 | 规则 |
| ---- | ---- |
| role_code | 必填，2–64 位，仅字母/数字/下划线，统一转大写，库内全局唯一 |
| role_name | 必填，长度 1–64 |
| status | 0:停用 1:启用，默认 1 |

### 1. 创建角色

`POST /api/v1/roles`

**请求体**

```json
{
  "role_code": "ADMIN",
  "role_name": "系统管理员",
  "status": 1,
  "create_by": "admin"
}
```

**响应**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "role_code": "ADMIN",
    "role_name": "系统管理员",
    "status": 1,
    "create_by": "admin",
    "update_by": null,
    "gmt_create": "2026-06-03T10:00:00",
    "gmt_modified": "2026-06-03T10:00:00"
  }
}
```

```bash
curl -X POST http://localhost:8000/api/v1/roles \
  -H "Content-Type: application/json" \
  -d '{"role_code":"ADMIN","role_name":"系统管理员","status":1,"create_by":"admin"}'
```

### 2. 查询角色详情

`GET /api/v1/roles/{id}`

| 参数 | 位置 | 类型 | 说明 |
| ---- | ---- | ---- | ---- |
| id | path | int | 角色 ID（≥1） |

**响应**：同创建角色的 `data` 结构。角色不存在时返回 `code=40400`。

```bash
curl http://localhost:8000/api/v1/roles/1
```

### 3. 分页查询角色

`GET /api/v1/roles`

| 参数 | 位置 | 类型 | 默认 | 说明 |
| ---- | ---- | ---- | ---- | ---- |
| page | query | int | 1 | 页码（≥1） |
| page_size | query | int | 10 | 每页条数（1–100） |
| role_name | query | string | - | 角色名称，模糊匹配 |
| status | query | int | - | 状态过滤，0:停用 1:启用 |

```bash
curl "http://localhost:8000/api/v1/roles?page=1&page_size=10&status=1"
```

### 4. 更新角色

`PUT /api/v1/roles/{id}`

仅更新请求体中传入的字段（局部更新）。

**请求体**

```json
{
  "role_name": "超级管理员",
  "status": 0,
  "update_by": "admin"
}
```

**响应**：返回更新后的完整角色对象。角色不存在返回 `40400`；角色编码冲突返回 `40901`。

```bash
curl -X PUT http://localhost:8000/api/v1/roles/1 \
  -H "Content-Type: application/json" \
  -d '{"role_name":"超级管理员","status":0,"update_by":"admin"}'
```

### 5. 删除角色（逻辑删除）

`DELETE /api/v1/roles/{id}`

将 `is_deleted` 置为 1，不做物理删除。

```bash
curl -X DELETE http://localhost:8000/api/v1/roles/1
```
