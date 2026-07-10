-- =============================================================
-- 视频分析任务 - 数据库初始化脚本
-- 数据库: MySQL 8.0+ | 字符集: utf8mb4
-- 说明: 新表按项目规范使用 t_ 前缀、下划线字段名及标准审计字段
-- =============================================================

CREATE DATABASE IF NOT EXISTS `user_management`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `user_management`;

DROP TABLE IF EXISTS `t_video_task`;
CREATE TABLE `t_video_task` (
    `id`           BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT             COMMENT '主键ID',
    `task_id`      VARCHAR(32)      NOT NULL                            COMMENT '任务ID（全局唯一）',
    `device_id`    VARCHAR(32)      NOT NULL                            COMMENT '设备ID',
    `video_url`    VARCHAR(2048)    NOT NULL                            COMMENT '待分析视频地址',
    `duration`     INT UNSIGNED     NOT NULL                            COMMENT '视频时长（秒）',
    `task_status`  TINYINT UNSIGNED NOT NULL DEFAULT 0                  COMMENT '任务状态 0:处理中(processing) 1:成功(success) 2:失败(failed)',
    `result_url`   VARCHAR(2048)             DEFAULT NULL               COMMENT '分析结果地址，任务成功前为空',
    `is_deleted`   TINYINT UNSIGNED NOT NULL DEFAULT 0                  COMMENT '逻辑删除 0:未删除 1:已删除',
    `gmt_create`   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP                      COMMENT '创建时间',
    `gmt_modified` DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_task_id` (`task_id`),
    KEY `idx_device_id_task_status` (`device_id`, `task_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='视频分析任务表';

-- 初始化示例数据（仅用于开发环境验证，生产环境执行前可移除）
INSERT INTO `t_video_task`
    (`task_id`, `device_id`, `video_url`, `duration`, `task_status`, `result_url`)
VALUES
    ('0123456789abcdef0123456789abcdef', 'device_001',
     'https://example.com/videos/demo-success.mp4', 30, 1,
     'https://example.com/results/demo-success.json'),
    ('fedcba9876543210fedcba9876543210', 'device_002',
     'https://example.com/videos/demo-failed.mp4', 45, 2, NULL);
