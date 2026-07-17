-- =============================================================
-- 视频分析任务 - 数据库初始化脚本
-- 数据库: MySQL 8.0+ | 字符集: utf8mb4
-- =============================================================
CREATE DATABASE IF NOT EXISTS `user_management`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `user_management`;

DROP TABLE IF EXISTS `t_video_task`;
CREATE TABLE `t_video_task` (
    `id`             BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `task_id`        VARCHAR(32)       NOT NULL                COMMENT '任务唯一标识',
    `device_id`      VARCHAR(32)       NOT NULL                COMMENT '设备唯一标识',
    `video_url`      VARCHAR(2048)     NOT NULL                COMMENT '视频地址',
    `duration`       DECIMAL(10,3) UNSIGNED NOT NULL            COMMENT '视频时长，单位秒',
    `task_status`    TINYINT UNSIGNED  NOT NULL DEFAULT 0      COMMENT '任务状态 0:等待处理 1:处理中 2:处理成功 3:处理失败',
    `result_url`     VARCHAR(2048)              DEFAULT NULL   COMMENT '分析结果地址',
    `failure_reason` VARCHAR(500)               DEFAULT NULL   COMMENT '失败原因',
    `is_deleted`     TINYINT UNSIGNED  NOT NULL DEFAULT 0      COMMENT '逻辑删除 0:未删除 1:已删除',
    `gmt_create`     DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `gmt_modified`   DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_task_id` (`task_id`),
    KEY `idx_device_status` (`device_id`, `task_status`),
    KEY `idx_task_status` (`task_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='视频分析任务表';

INSERT INTO `t_video_task` (`task_id`, `device_id`, `video_url`, `duration`, `task_status`)
VALUES ('0123456789abcdef0123456789abcdef', 'device000000000000000000000001',
        'https://example.com/videos/demo.mp4', 3.000, 0);
