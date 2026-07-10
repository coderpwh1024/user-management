-- /api/video/upload 的 wrk POST 压测脚本。
-- 每个请求使用唯一 deviceId，避免单设备并发限制干扰接口吞吐测量。

wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"

local threads = {}
local thread_index = 0

function setup(thread)
    thread_index = thread_index + 1
    thread:set("thread_id", thread_index)
    table.insert(threads, thread)
end

function init(args)
    request_index = 0
    business_success = 0
    business_failure = 0
    response_429 = 0
    response_42200 = 0
    response_50000 = 0
    response_50001 = 0
    response_50002 = 0
    response_other_error = 0
    invalid_response = 0
    wrk.thread:set("business_success", 0)
    wrk.thread:set("business_failure", 0)
    wrk.thread:set("response_429", 0)
    wrk.thread:set("response_42200", 0)
    wrk.thread:set("response_50000", 0)
    wrk.thread:set("response_50001", 0)
    wrk.thread:set("response_50002", 0)
    wrk.thread:set("response_other_error", 0)
    wrk.thread:set("invalid_response", 0)
end

function request()
    request_index = request_index + 1
    local device_id = string.format(
        "load-%02d-%010d",
        thread_id,
        request_index
    )
    local body = string.format(
        '{"deviceId":"%s","videoUrl":"https://example.com/load-test.mp4","duration":30}',
        device_id
    )
    return wrk.format(nil, nil, nil, body)
end

function response(status, headers, body)
    if body and string.find(body, '"code":0', 1, true) then
        business_success = business_success + 1
    else
        business_failure = business_failure + 1
        if body and string.find(body, '"code":429', 1, true) then
            response_429 = response_429 + 1
        elseif body and string.find(body, '"code":42200', 1, true) then
            response_42200 = response_42200 + 1
        elseif body and string.find(body, '"code":50000', 1, true) then
            response_50000 = response_50000 + 1
        elseif body and string.find(body, '"code":50001', 1, true) then
            response_50001 = response_50001 + 1
        elseif body and string.find(body, '"code":50002', 1, true) then
            response_50002 = response_50002 + 1
        elseif not body or not string.find(body, '"code":', 1, true) then
            invalid_response = invalid_response + 1
        else
            response_other_error = response_other_error + 1
        end
    end

    wrk.thread:set("business_success", business_success)
    wrk.thread:set("business_failure", business_failure)
    wrk.thread:set("response_429", response_429)
    wrk.thread:set("response_42200", response_42200)
    wrk.thread:set("response_50000", response_50000)
    wrk.thread:set("response_50001", response_50001)
    wrk.thread:set("response_50002", response_50002)
    wrk.thread:set("response_other_error", response_other_error)
    wrk.thread:set("invalid_response", invalid_response)
end

function done(summary, latency, requests)
    local success = 0
    local failure = 0
    local limited = 0
    local validation_failed = 0
    local internal_failed = 0
    local create_failed = 0
    local redis_failed = 0
    local other_failed = 0
    local invalid = 0

    for _, thread in ipairs(threads) do
        success = success + (thread:get("business_success") or 0)
        failure = failure + (thread:get("business_failure") or 0)
        limited = limited + (thread:get("response_429") or 0)
        validation_failed = validation_failed + (thread:get("response_42200") or 0)
        internal_failed = internal_failed + (thread:get("response_50000") or 0)
        create_failed = create_failed + (thread:get("response_50001") or 0)
        redis_failed = redis_failed + (thread:get("response_50002") or 0)
        other_failed = other_failed + (thread:get("response_other_error") or 0)
        invalid = invalid + (thread:get("invalid_response") or 0)
    end

    io.write(string.format("Business success: %d\n", success))
    io.write(string.format("Business failure: %d\n", failure))
    io.write(string.format("Business code 429: %d\n", limited))
    io.write(string.format("Business code 42200: %d\n", validation_failed))
    io.write(string.format("Business code 50000: %d\n", internal_failed))
    io.write(string.format("Business code 50001: %d\n", create_failed))
    io.write(string.format("Business code 50002: %d\n", redis_failed))
    io.write(string.format("Other business errors: %d\n", other_failed))
    io.write(string.format("Invalid response: %d\n", invalid))
end
