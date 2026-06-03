-- =============================================================
-- 角色管理 - 数据库初始化脚本
-- 数据库: MySQL 8.0+ | 字符集: utf8mb4
-- 说明: 新表按 CLAUDE.md 第四章规范（gmt_* / is_deleted / uk_/idx_ / 0900_ai_ci）
-- =============================================================

CREATE DATABASE IF NOT EXISTS `user_management`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `user_management`;

DROP TABLE IF EXISTS `t_role`;
CREATE TABLE `t_role` (
    `id`           BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT             COMMENT '主键ID',
    `role_code`    VARCHAR(64)      NOT NULL                            COMMENT '角色编码（全局唯一）',
    `role_name`    VARCHAR(64)      NOT NULL                            COMMENT '角色名称',
    `status`       TINYINT UNSIGNED NOT NULL DEFAULT 1                  COMMENT '状态 0:停用 1:启用',
    `is_deleted`   TINYINT UNSIGNED NOT NULL DEFAULT 0                  COMMENT '逻辑删除 0:未删除 1:已删除',
    `create_by`    VARCHAR(64)               DEFAULT NULL               COMMENT '创建人',
    `update_by`    VARCHAR(64)               DEFAULT NULL               COMMENT '更新人',
    `gmt_create`   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP                      COMMENT '创建时间',
    `gmt_modified` DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_role_code` (`role_code`),
    KEY `idx_role_name` (`role_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='角色表';

-- 初始化示例数据（可选）
INSERT INTO `t_role` (`role_code`, `role_name`, `status`, `create_by`)
VALUES
    ('ADMIN',  '系统管理员', 1, 'system'),
    ('GUEST',  '访客',       0, 'system');
