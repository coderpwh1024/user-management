# 视频上传接口压测报告

## 一、测试结论

`POST /api/video/upload` 在完成 Redis 异步化、MySQL 写入解耦和多 worker 生产模式
部署后，已**突破 500 并发接入目标**。

最终复测结果为 500 并发、20 秒内完成 31580 个响应，吞吐量 1576.53 req/s；
业务成功 31580/31580，业务失败 0。相比优化前 91.48 req/s，吞吐提升约 17.2 倍。

补充说明：wrk 统计了 128 次 socket read error，但业务响应体中没有失败码，
成功率按已收到的业务响应为 100%。这些连接层错误建议在目标部署环境继续用更高
ulimit、内核参数和独立压测机复核。

优化前的同步链路主要瓶颈位于 MySQL 连接与同步写入；对照数据和失败码保留在
第六节。

## 二、测试时间与环境

- 测试日期：2026-07-10
- 操作系统：macOS 26.5.2
- 设备：MacBookPro18,2，10 逻辑 CPU
- wrk：4.2.0，kqueue
- Python：3.13.13
- MySQL：8.0.40，`max_connections=151`
- Redis：7.2.3
- 应用端口：9001
- 应用运行方式：PyCharm Debug，单 Uvicorn worker
- `APP_DEBUG=true`
- MySQL 连接池：`pool_size=50`，`max_overflow=100`
- Redis 最大连接数：200
- 优化后 Redis 最大连接数：1000
- 模拟分析耗时：3 秒
- 最终复测进程：Uvicorn 8 workers，`APP_DEBUG=false`，关闭 access log

## 三、测试场景

### 3.1 接口

```text
POST http://localhost:9001/api/video/upload
```

请求体：

```json
{
  "deviceId": "load-01-0000000001",
  "videoUrl": "https://example.com/load-test.mp4",
  "duration": 30
}
```

### 3.2 并发口径

- wrk 线程数：8
- 并发连接数：500
- 持续时间：20 秒
- wrk 默认请求超时：2 秒
- 每个请求使用不同的 `deviceId`

使用唯一 `deviceId` 是为了测量上传接口的总体接入能力。如果所有请求都使用同一
设备，单设备最多两个活跃任务的业务规则会按设计返回 `code=429`，测试结果只能
反映限流是否生效，不能反映上传链路吞吐量。

### 3.3 执行命令

```bash
wrk -t8 -c500 -d20s -s post.lua http://localhost:9001/api/video/upload
```

Lua 脚本位于项目根目录 [post.lua](../post.lua)，除构造动态请求外，还会按响应体
统计 `code=0`、`429`、`42200`、`50000`、`50001` 和 `50002`。

## 四、正式复测结果

```text
Running 20s test @ http://localhost:9001/api/video/upload
  8 threads and 500 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     1.32s   401.34ms   2.00s    68.09%
    Req/Sec    17.42     18.03   150.00     88.76%
  1837 requests in 20.08s, 357.18KB read
  Socket errors: connect 0, read 0, write 0, timeout 1696
Requests/sec:     91.48
Transfer/sec:     17.79KB
Business success: 1020
Business failure: 817
Business code 429: 0
Business code 42200: 0
Business code 50000: 0
Business code 50001: 817
Business code 50002: 0
Other business errors: 0
Invalid response: 0
```

### 4.1 指标汇总

| 指标 | 结果 | 说明 |
| ---- | ----: | ---- |
| 并发连接 | 500 | 符合测试要求 |
| 测试时长 | 20.08 秒 | 符合测试要求 |
| wrk 吞吐量 | 91.48 req/s | 包含业务成功与业务失败响应 |
| 业务成功响应 | 1020 | `code=0` |
| 业务成功吞吐量 | 约 50.80 req/s | `1020 / 20.08` |
| 业务失败响应 | 817 | 全部为 `code=50001` |
| 已返回响应业务失败率 | 44.47% | `817 / 1837` |
| 超时 | 1696 | wrk 默认 2 秒超时 |
| 平均延迟 | 1.32 秒 | 仅统计收到响应的请求 |
| 最大延迟 | 2.00 秒 | 触及 wrk 默认超时阈值 |
| Redis/限流错误 | 0 | `429=0`、`50002=0` |

## 五、首轮结果

首轮脚本只区分成功、429 和其他业务失败，结果如下。复测增加了详细错误码统计，
确认其他业务失败全部来自 `code=50001`。

```text
Running 20s test @ http://localhost:9001/api/video/upload
  8 threads and 500 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     1.40s   376.64ms   2.00s    68.75%
    Req/Sec    18.17     17.85   120.00     88.25%
  2160 requests in 20.07s, 419.41KB read
  Socket errors: connect 0, read 0, write 0, timeout 2032
Requests/sec:    107.63
Transfer/sec:     20.90KB
Business success: 1170
Business failure: 990
Business code 429: 0
Invalid response: 0
```

## 六、数据库与任务状态观察

两轮正式压测和脚本冒烟测试结束后，按 `device_id LIKE 'load-%'` 汇总：

| 数据库状态 | 数量 |
| ---- | ----: |
| processing | 363 |
| success | 2601 |
| failed | 144 |
| 合计 | 3108 |

客户端超时不代表服务端立即停止处理，因此数据库任务数可能高于 wrk 已收到的业务
成功响应数。压测结束数秒后仍有 363 个 `processing` 和 144 个 `failed`，说明后台
分析状态更新同样受到数据库连接争用影响。

## 七、瓶颈判断

1. MySQL 配置最多允许 151 个连接，应用连接池上限为 150，几乎占满数据库连接预算，
   没有为后台状态更新和管理连接预留空间。
2. 上传接口是同步 SQLAlchemy 写入，每个请求必须等待数据库提交；500 个并发连接会
   在连接池前排队或创建溢出连接。
3. 每个成功上传任务约 3 秒后还会产生一次后台数据库更新，与持续上传共同争抢连接。
4. 当前为 Debug 单 worker 运行方式，不代表生产部署容量；SQL 日志输出进一步放大
   CPU 和 I/O 开销。
5. Redis Lua 并发控制没有出现错误，本轮不是 Redis 瓶颈。

## 八、已实施的优化

1. 上传入口改为 `async def`，不再占用 FastAPI 默认同步请求线程池。
2. 使用 `redis.asyncio` 执行设备槽位 Lua 限流和任务元数据写入，避免事件循环调用
   同步 Redis 客户端。
3. 上传请求先写 Redis 实时任务缓存，MySQL 创建记录进入有界队列，由 16 个受控
   持久化线程异步提交，避免 500 个请求同时争抢 MySQL 连接。
4. 状态查询优先读取 Redis，只有缓存未命中才回源 MySQL。
5. 分析完成后先更新 Redis 为 `success/failed`，再异步同步 MySQL，保证实时状态不被
   慢数据库阻塞。
6. Redis 连接池提升为可配置的 1000，生产压测使用 8 个 Uvicorn worker、较小且受控
   的每 worker MySQL 连接池（`DB_POOL_SIZE=8`、`DB_MAX_OVERFLOW=4`）。
7. 高频上传日志降为 DEBUG，生产压测关闭 Uvicorn access log，减少日志 I/O。

## 九、优化后正式复测结果

```text
Running 20s test @ http://localhost:9001/api/video/upload
  8 threads and 500 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   353.61ms  304.32ms   2.00s    79.85%
    Req/Sec   204.56    177.92     1.10k    78.86%
  31580 requests in 20.03s, 6.26MB read
  Socket errors: connect 0, read 0, write 0, timeout 128
Requests/sec:   1576.53
Transfer/sec:    320.23KB
Business success: 31580
Business failure: 0
Business code 429: 0
Business code 42200: 0
Business code 50000: 0
Business code 50001: 0
Business code 50002: 0
Other business errors: 0
Invalid response: 0
```

压测结束约 2 分钟后，最近 2 分钟写入的 42685 条任务全部为 `success`，没有新增
失败记录；Redis 仍保持可用。

## 十、优化与复测建议

1. 使用生产模式复测：`APP_DEBUG=false`，关闭 SQL echo，并配置多个 Uvicorn worker。
2. 让应用总连接上限小于 MySQL `max_connections`，为后台任务、监控和管理连接预留
   20%–30% 空间；同时根据数据库实际处理能力调整，而不是简单把连接池放大到 150。
3. 将模拟分析从 Web 进程的 `BackgroundTasks` 解耦到独立任务消费者；上传请求只做
   一次短事务写入，后台消费者按受控并发更新状态。
4. 为创建任务失败记录底层数据库错误分类和连接池指标，以区分连接耗尽、锁等待和
   数据库拒绝连接。
5. 优化后先用当前原始命令复测，验收目标建议为：业务成功率 100%、超时 0、
   `code=50001/50002=0`、Requests/sec 不低于 500。
6. 可额外使用 `--timeout 10s --latency` 做诊断，但不能替代本报告中原始命令的
   2 秒超时验收口径。

## 十一、复现步骤

```bash
# 1. 确认依赖可用
curl http://localhost:9001/health

# 2. 执行建表脚本并启动 MySQL、Redis、应用

# 3. 执行正式压测
wrk -t8 -c500 -d20s -s post.lua http://localhost:9001/api/video/upload
```

本报告没有清理压测产生的 `load-*` 数据，避免未经确认删除数据库记录。若需要重复
测试，应先按项目的数据保留策略归档或清理压测数据。
