# 视频任务上报压测报告

## 结论

2026-07-17 在本机 MySQL 8、Redis 7.2.3 与隔离应用实例上，视频任务上报接口以
**500 并发连接**持续压测 20 秒，完成 **31,650** 次请求，吞吐为
**1,576.99 req/s**，未出现 socket 错误。压测中创建的 **861** 个视频任务在队列
排空后全部处理成功，失败数为 0。

本次压测覆盖并超过“500 并发上报”要求。注意：这不是 500 个任务全部同时成功的
要求；业务规则限制同一设备最多存在 2 个未完成任务。压测脚本使用 250 个模拟设备，
对应 500 个可并发占用的设备槽位，其余请求应正常得到业务码 `429`。

## 环境与配置

| 项目 | 值 |
| --- | --- |
| 应用 | FastAPI / Uvicorn，本次代码工作区版本 |
| 服务端口 | `9002`（`9001` 被本机 PyCharm 调试实例占用，未中断该进程） |
| MySQL | 本机 MySQL 8，连接池 `pool_size=50`、`max_overflow=100` |
| Redis | 7.2.3，本机 `127.0.0.1:6379` |
| HTTP 请求线程池 | `REQUEST_THREAD_POOL_SIZE=160` |
| 视频分析线程池 | `VIDEO_TASK_WORKER_COUNT=64` |
| 负载工具 | wrk 4.2.0 |

`REQUEST_THREAD_POOL_SIZE` 用于提高同步 SQLAlchemy/Redis 请求的并发执行容量，且与
数据库最大连接容量（150）保持接近，避免默认同步线程池容量成为短请求瓶颈。

## 压测脚本

脚本位于 [scripts/post_video_benchmark.lua](../scripts/post_video_benchmark.lua)。每次请求
随机选择 250 台设备之一，请求体如下：

```json
{
  "deviceId": "benchmark-v2-device-001",
  "videoUrl": "https://example.com/benchmark/input.mp4",
  "duration": 3
}
```

使用 250 台设备是为了将业务限流边界扩展至 `250 × 2 = 500` 个未完成任务，既能覆盖
500 并发场景，也能持续验证 `429` 限流分支。

## 执行命令

```bash
wrk -t8 -c500 -d20s --latency \
  -s scripts/post_video_benchmark.lua \
  http://127.0.0.1:9002/api/video/upload
```

若 `9001` 未被其他本地进程占用，可将最后的地址替换为需求中的：

```bash
http://localhost:9001/api/video/upload
```

## wrk 原始结果

```text
Running 20s test @ http://127.0.0.1:9002/api/video/upload
  8 threads and 500 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   314.29ms  119.03ms  972.00ms   81.19%
    Req/Sec   214.09     95.17   440.00     61.38%
  Latency Distribution
     50%  274.85ms
     75%  385.60ms
     90%  445.20ms
     99%  771.75ms
  31650 requests in 20.07s, 6.60MB read
Requests/sec:   1576.99
Transfer/sec:    336.81KB
```

`wrk` 未报告 connect/read/write/timeout socket 错误。

## 业务结果核验

压测结束后，执行以下 SQL 查询由本轮脚本写入的任务：

```sql
SELECT COUNT(*) AS accepted_total,
       SUM(task_status = 0) AS pending,
       SUM(task_status = 1) AS processing,
       SUM(task_status = 2) AS success,
       SUM(task_status = 3) AS failed
FROM t_video_task
WHERE device_id LIKE 'benchmark-v2-device-%';
```

队列排空后的结果：

| accepted_total | pending | processing | success | failed |
| ---: | ---: | ---: | ---: | ---: |
| 861 | 0 | 0 | 861 | 0 |

因此，所有成功上报并持久化的任务均完成模拟分析。总请求与创建任务数的差额，是同设备
并发槽位已满时返回的预期业务限流响应（`code=429`）；该业务错误仍遵循项目统一响应并
返回 HTTP 200。

## 清理说明

压测数据使用 `benchmark-v2-device-` 前缀，与业务设备数据隔离。需要清理时，应在确认
目标仅为压测数据后执行逻辑删除，而不是物理删除：

```sql
UPDATE t_video_task
SET is_deleted = 1
WHERE device_id LIKE 'benchmark-v2-device-%';
```
