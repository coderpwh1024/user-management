"""视频上传接口压测脚本（Locust）。

被测接口：``POST /api/video/upload``（异步受理，立即返回 taskId）。

关键设计
--------
- **唯一 deviceId（吞吐场景）**：``VideoUploadUser`` 每次请求生成全新 ``deviceId``，
  绕开「单设备最多 2 个在途任务」限流，测接口真实吞吐上限。
- **固定 deviceId（限流场景）**：``DeviceLimitUser`` 复用同一 ``deviceId`` 持续打压，
  用于验证 429 限流是否按预期生效（不参与吞吐统计，按需启用）。
- 业务异常 HTTP 仍返回 200，错误体现在响应体 ``code``。这里用 ``catch_response``
  按业务码判定成功 / 失败，使 Locust 的成功率真实反映业务结果（code=0 才算成功）。

运行示例（吞吐场景，500 并发，60s）
-----------------------------------
    .venv/bin/locust -f loadtest/locustfile.py \\
        --headless -u 500 -r 100 -t 60s \\
        -H http://127.0.0.1:9001 \\
        --csv loadtest/result --html loadtest/report.html VideoUploadUser
"""
import uuid

from locust import HttpUser, constant, task


class VideoUploadUser(HttpUser):
    """吞吐场景：每请求唯一 deviceId，不触发单设备限流。"""

    # 闭环压测：拿到响应立即发下一个，制造最大压力
    wait_time = constant(0)

    @task
    def upload(self) -> None:
        device_id = uuid.uuid4().hex
        payload = {
            "deviceId": device_id,
            "videoUrl": f"https://cdn.example.com/{device_id}.mp4",
            "duration": 5,
        }
        with self.client.post(
            "/api/video/upload", json=payload, catch_response=True, name="/api/video/upload"
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                return
            try:
                body = resp.json()
            except Exception:  # noqa: BLE001
                resp.failure("响应非 JSON")
                return
            code = body.get("code")
            if code == 0 and body.get("data", {}).get("taskId"):
                resp.success()
            elif code == 429:
                # 唯一 deviceId 理论上不应出现 429，出现即异常
                resp.failure("429 限流（吞吐场景不应出现）")
            else:
                resp.failure(f"业务码 {code}: {body.get('message')}")


class DeviceLimitUser(HttpUser):
    """限流验证场景：固定 deviceId 持续打压，预期出现大量 429。

    仅用于验证限流逻辑，运行时单独指定该类，例如：
        .venv/bin/locust -f loadtest/locustfile.py --headless \\
            -u 20 -r 20 -t 15s -H http://127.0.0.1:9001 DeviceLimitUser
    """

    wait_time = constant(0)
    # 所有该类用户共享同一设备，制造单设备并发
    fixed_device_id = "loadtest-fixed-device"

    @task
    def upload_same_device(self) -> None:
        payload = {
            "deviceId": self.fixed_device_id,
            "videoUrl": "https://cdn.example.com/fixed.mp4",
            "duration": 5,
        }
        with self.client.post(
            "/api/video/upload", json=payload, catch_response=True,
            name="/api/video/upload [fixed-device]",
        ) as resp:
            try:
                code = resp.json().get("code")
            except Exception:  # noqa: BLE001
                resp.failure("响应非 JSON")
                return
            # 限流场景：code=0（受理）与 code=429（限流）都属预期行为
            if code in (0, 429):
                resp.success()
            else:
                resp.failure(f"业务码 {code}")
