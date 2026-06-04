# 视频上传接口压测报告

> 被测接口：`POST /api/video/upload`（异步受理上传，立即返回 `taskId`）
> 压测目标：并发峰值靠近 500，评估吞吐 / 延迟 / 稳定性，定位瓶颈并给出生产配置建议。

---

## 一、压测概要

| 项 | 内容 |
| ---- | ---- |
| 被测接口 | `POST /api/video/upload` |
| 压测工具 | **Locust 2.44.0**（Python 生态标准压测工具，与项目技术栈一致） |
| 负载模型 | 闭环（closed-loop）：每个虚拟用户拿到响应后立即发下一个请求 |
| 并发峰值 | 500 虚拟用户（VU），爬升速率 100 VU/s |
| 单轮时长 | 60 秒 |
| 压测机 | MacBook Pro，10 核 CPU，本地回环（client 与 server 同机） |
| 数据库 | MySQL 8.0.40，`max_connections=151` |
| 运行端 | 应用 `python 3.13` + uvicorn；Locust 用 `--processes 4` 多进程，避免客户端自身成为瓶颈 |

### 为何选 Locust

- **与项目栈一致**：场景用 Python 编写，便于表达「每请求唯一 `deviceId`」「按业务 `code` 判定成败」等接口特有逻辑；
- **能正确判定业务成败**：本接口业务异常时 HTTP 仍返回 200，错误体现在响应体 `code`。`ab` / `wrk` 只看 HTTP 状态码会把限流 429、业务失败误判为成功。Locust 的 `catch_response` 可按 `code` 精确判定；
- **报告完善**：自带 CSV / HTML 报告与百分位统计，开箱即用。

---

## 二、压测场景设计

接口存在「**单设备最多 2 个在途任务**」限流（超限返回 `code=429`）。若压测用同一个 `deviceId`，500 并发会几乎全部被限流，无法测真实吞吐。因此设计两类场景（见 `loadtest/locustfile.py`）：

| 场景类 | deviceId 策略 | 目的 |
| ---- | ---- | ---- |
| `VideoUploadUser` | **每请求唯一**（`uuid4().hex`） | 绕开单设备限流，测接口**真实吞吐上限** |
| `DeviceLimitUser` | **固定同一个** | 验证 429 限流逻辑是否生效 |

判定规则（吞吐场景）：仅 `code=0` 且返回了 `taskId` 才算成功；出现 429 或其他业务码、非 200、非 JSON 均记为失败。

---

## 三、压测结果

对吞吐场景（`VideoUploadUser`）在三种服务端配置下各跑一轮 `-u 500 -r 100 -t 60s`：

| 轮次 | 服务端配置 | 总请求 | 失败率 | 吞吐(req/s) | 平均(ms) | P50 | P90 | P99 | 最大(ms) |
| ---- | ---- | ----: | ----: | ----: | ----: | ----: | ----: | ----: | ----: |
| **轮1 基线** | 单 worker，连接池 30，默认线程池 ~14 | 24,058 | **0.00%** | ~400 | 1192 | 1300 | 1400 | 1500 | 1894 |
| **轮2 调优** | 单 worker，连接池 128，线程池 64 | 26,912 | 1.02% | ~450 | 1034 | 820 | 1100 | 7800 | 35122 |
| **轮3 多 worker** | **4 worker**，每 worker 连接池 30 / 线程池 ~14 | 57,511 | **0.00%** | **~958** | **501** | **520** | **650** | **800** | **1089** |

> 对应 HTML 报告：`loadtest/report_baseline.html`、`report_tuned.html`、`report_workers.html`；
> 原始 CSV：`loadtest/result_baseline_stats.csv` 等。

### 完整百分位（ms）

| 配置 | P50 | P75 | P90 | P95 | P98 | P99 | P99.9 | Max |
| ---- | --: | --: | --: | --: | --: | --: | --: | --: |
| 轮1 基线 | 1300 | 1300 | 1400 | 1400 | 1500 | 1500 | 1700 | 1894 |
| 轮2 调优 | 820 | 950 | 1100 | 1300 | 6800 | 7800 | 31000 | 35122 |
| 轮3 多 worker | 520 | 590 | 650 | 690 | 750 | 800 | 930 | 1089 |

### 异步链路稳定性

三轮压测累计产生 **109,658** 条任务记录，后台异步处理（`sleep(3)` 模拟上传 + 分析后回写状态）**全部成功落地为 `status=1`，0 失败**。说明「立即受理 + 后台异步处理 + 状态回写」链路在高并发下稳定可靠。MySQL 连接峰值 **80 / 151**，全程未触及上限。

### 429 限流验证

对单 worker 实例用固定 `deviceId` 并发 30 个请求：

```
响应码分布: {429: 28, 0: 2}
```

恰好 **2 个受理 + 28 个限流**，单 worker 下严格限流到 2，符合设计预期。

---

## 四、瓶颈分析

### 1. 基线（单 worker）：稳定但延迟受限于线程池排队
`upload` 受理时的同步 DB 操作（`count + insert`）通过 `asyncio.to_thread` 丢到事件循环**默认线程池**执行，其大小默认仅 `min(32, cpu+4)≈14`。500 并发下大量请求在线程池排队，导致中位延迟被抬到 1.3s。但系统始终稳定，**0 失败**。

### 2. 调优（放大线程池 + 连接池）：中位改善，但尾延迟与失败劣化
将线程池放大到 64、连接池放大到 128 后：中位延迟降到 820ms、吞吐 +12%。但代价是 **P99 飙到 7.8s、最大 35s、1% 失败**。

根因排查：MySQL 连接峰值仅 80/151（**未到上限**）、服务端日志**无任何异常**、DB 落库 **0 失败**。说明失败与长尾并非来自数据库，而是 **单进程事件循环 + 过多线程** 的调度争用与 socket accept backlog——单进程内堆线程对付同步阻塞 IO（PyMySQL），线程上下文切换与 GIL 争用反而制造了长尾，少数请求在客户端侧超时。**结论：单进程纵向堆线程是错误方向。**

### 3. 多 worker（横向扩展）：吞吐、延迟、稳定性全面最优
改用 4 个 worker 进程（每进程沿用保守的 30 连接 / 14 线程）后：吞吐 **958 req/s（基线 2.4×）**、P50 **520ms**、P99 **800ms**、最大 **1.1s**、**0 失败**。多进程把负载摊到多核、各自独立事件循环与线程池，彻底消除了单进程调度瓶颈。

**一句话结论**：支撑 ~500 并发，正确做法是 **多 worker 横向扩展**，而非在单进程内放大线程池 / 连接池。

---

## 五、生产配置建议

1. **多 worker 部署**（首选）：`uvicorn app.main:app --workers N`，`N` 取 CPU 核数附近。本测试 4 worker 即可在 500 并发下 0 失败、P99<1s。
2. **连接池量力而行**：每 worker `db_pool_size + db_max_overflow` 之和 × worker 数 **必须 < MySQL `max_connections`**（本机 151）。保守的 30/worker × 4 = 120 已足够且安全；盲目放大无益。
3. **彻底解决同步阻塞**（进阶）：用异步 DB 驱动（`asyncmy` / `aiomysql` + SQLAlchemy async）替代「PyMySQL + `to_thread`」，可去掉线程池这一中间瓶颈，单 worker 吞吐即可大幅提升。
4. **⚠️ 多 worker 下的限流一致性**：当前「单设备最多 2 个在途」依赖 DB 实时 `COUNT`（跨进程共享，全局基本生效）+ 进程内 `asyncio.Lock`（**不跨进程**）。多 worker 下「count + insert」缺少全局原子性，并发窗口内单设备**可能轻微超过 2**。如需严格全局限流，应改用 **Redis 原子计数 / 分布式锁**，或在 DB 层用条件插入 / 行锁保证原子。
5. **日志**：压测/生产高并发下关闭 access log、应用日志级别设 `WARNING` 以上，避免 I/O 拖慢（本测试已采用）。

---

## 六、复现步骤

```bash
# 0) 安装压测依赖
.venv/bin/pip install -r loadtest/requirements-loadtest.txt

# 1) 建表（首次）
mysql -uroot -p user_management < sql/t_video_task.sql

# 2-A) 基线：单 worker 启动服务
APP_DEBUG=false LOG_LEVEL=WARNING \
  .venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port 9002 --no-access-log --log-level warning

# 2-B) 多 worker（推荐）
APP_DEBUG=false LOG_LEVEL=WARNING \
  .venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port 9004 --workers 4 --no-access-log --log-level warning

# 3) 跑吞吐压测（500 VU / 60s）
.venv/bin/locust -f loadtest/locustfile.py \
  --headless -u 500 -r 100 -t 60s --processes 4 \
  -H http://127.0.0.1:9004 \
  --csv loadtest/result --html loadtest/report.html \
  VideoUploadUser

# 4) 验证 429 限流（固定 deviceId 场景）
.venv/bin/locust -f loadtest/locustfile.py --headless \
  -u 20 -r 20 -t 15s -H http://127.0.0.1:9004 DeviceLimitUser
```

可选交互式 Web UI：去掉 `--headless`，浏览器打开 `http://localhost:8089`。

---

## 七、压测数据清理

压测向 `t_video_task` 写入了约 11 万行垃圾数据，可按需清理：

```sql
-- 仅清理压测数据（保留示例数据：task_id 为纯数字 UUID 占位的可单独保留）
DELETE FROM t_video_task WHERE device_id LIKE 'device-%' = 0;  -- 视情况调整条件
-- 或直接清空整表（开发环境）
TRUNCATE TABLE t_video_task;
```

---

## 附：产物清单

| 文件 | 说明 |
| ---- | ---- |
| `loadtest/locustfile.py` | 压测脚本（吞吐场景 + 限流验证场景） |
| `loadtest/serve_tuned.py` | 调优版启动入口（放大线程池，用于轮2对比） |
| `loadtest/requirements-loadtest.txt` | 压测依赖（locust==2.44.0） |
| `loadtest/report_baseline.html` / `report_tuned.html` / `report_workers.html` | 三轮 HTML 报告 |
| `loadtest/result_*_stats.csv` 等 | 三轮原始 CSV 数据 |
