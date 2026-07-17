-- 视频任务上报压测脚本。
-- 使用 250 台模拟设备，使 500 并发连接可覆盖每设备最多两个未完成任务的边界。
wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"

function request()
    local device_number = math.random(1, 250)
    local body = string.format(
        '{"deviceId":"benchmark-v2-device-%03d","videoUrl":"https://example.com/benchmark/input.mp4","duration":3}',
        device_number
    )
    return wrk.format(nil, nil, nil, body)
end
