-- =============================================================
-- 用户管理 - 数据库初始化脚本
-- 数据库: MySQL 8.0+
-- 字符集: utf8mb4
-- =============================================================

-- 1. 创建数据库（如不存在）
CREATE DATABASE IF NOT EXISTS `user_management`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_general_ci;

USE `user_management`;

-- 2. 用户表
DROP TABLE IF EXISTS `t_user`;
CREATE TABLE `t_user` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `name`        VARCHAR(64)  NOT NULL                COMMENT '姓名',
    `age`         TINYINT UNSIGNED      DEFAULT NULL   COMMENT '年龄',
    `phone`       VARCHAR(20)  NOT NULL                COMMENT '手机号',
    `id_card`     VARCHAR(18)  NOT NULL                COMMENT '身份证号',
    `gender`      TINYINT      NOT NULL DEFAULT 0      COMMENT '性别 0:未知 1:男 2:女',
    `is_delete`   TINYINT      NOT NULL DEFAULT 0      COMMENT '逻辑删除 0:未删除 1:已删除',
    `create_by`   VARCHAR(64)           DEFAULT NULL   COMMENT '创建人',
    `update_by`   VARCHAR(64)           DEFAULT NULL   COMMENT '更新人',
    `create_date` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP                      COMMENT '创建时间',
    `update_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_id_card` (`id_card`),
    KEY `idx_phone` (`phone`),
    KEY `idx_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='用户表';

-- 3. 初始化示例数据（可选）
INSERT INTO `t_user` (`name`, `age`, `phone`, `id_card`, `gender`, `create_by`)
VALUES
    ('张三', 28, '13800138000', '110101199001011237', 1, 'system'),
    ('李四', 32, '13900139000', '310101198805054323', 2, 'system');
