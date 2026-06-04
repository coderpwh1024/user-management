-- =============================================================
-- 视频异步上传任务 - 数据库初始化脚本
-- 数据库: MySQL 8.0+ | 字符集: utf8mb4
-- 说明: 新表按 CLAUDE.md 第四章规范（gmt_* / is_deleted / uk_/idx_ / 0900_ai_ci）
--       task_id 为 UUID，全局唯一；status 三态支持异步在途统计与并发限流。
-- =============================================================

CREATE DATABASE IF NOT EXISTS `user_management`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `user_management`;

DROP TABLE IF EXISTS `t_video_task`;
CREATE TABLE `t_video_task` (
    `id`           BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT             COMMENT '主键ID',
    `task_id`      VARCHAR(64)      NOT NULL                            COMMENT '任务ID（UUID，全局唯一）',
    `device_id`    VARCHAR(64)      NOT NULL                            COMMENT '设备ID',
    `video_url`    VARCHAR(512)     NOT NULL                            COMMENT '原始视频链接',
    `duration`     INT UNSIGNED             DEFAULT NULL                COMMENT '视频时长(秒)',
    `status`       TINYINT UNSIGNED NOT NULL DEFAULT 0                  COMMENT '任务状态 0:处理中 1:成功 2:失败',
    `result_url`   VARCHAR(512)             DEFAULT NULL                COMMENT '分析结果链接',
    `error_msg`    VARCHAR(512)             DEFAULT NULL                COMMENT '失败原因',
    `is_deleted`   TINYINT UNSIGNED NOT NULL DEFAULT 0                  COMMENT '逻辑删除 0:未删除 1:已删除',
    `gmt_create`   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP                      COMMENT '创建时间',
    `gmt_modified` DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_task_id` (`task_id`),
    -- 组合索引：并发限流按 (device_id, status) 实时 COUNT 在途任务，遵循最左前缀
    KEY `idx_device_id_status` (`device_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='视频异步上传任务表';

-- 初始化示例数据（可选）
INSERT INTO `t_video_task` (`task_id`, `device_id`, `video_url`, `duration`, `status`, `result_url`)
VALUES
    ('11111111111111111111111111111111', 'device-001', 'https://cdn.example.com/v/demo1.mp4', 30, 1, 'https://result.example.com/11111111111111111111111111111111.json'),
    ('22222222222222222222222222222222', 'device-001', 'https://cdn.example.com/v/demo2.mp4', 12, 0, NULL);
