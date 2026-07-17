"""应用配置模块。

通过 pydantic-settings 从环境变量 / .env 文件加载配置，
集中管理数据库、日志等运行时参数。
"""
from functools import lru_cache
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置。"""

    # 应用
    app_name: str = "user-management"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 9001

    # 数据库
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "root123456"
    db_name: str = "user_management"

    # 连接池
    db_pool_size: int = 50
    db_max_overflow: int = 100
    db_pool_recycle: int = 3600

    # Redis
    redis_dsn: str | None = None
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    redis_max_connections: int = 1000
    redis_socket_timeout: float = 2.0
    redis_socket_connect_timeout: float = 2.0
    redis_health_check_interval: int = 30

    # 视频分析任务
    video_task_worker_count: int = 64
    request_thread_pool_size: int = 160

    # 日志
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """构造 SQLAlchemy 数据库连接串。"""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        """构造 Redis 连接串。

        优先使用 ``REDIS_DSN``，便于云 Redis 或带用户名的部署场景直接覆盖。
        """
        if self.redis_dsn:
            return self.redis_dsn

        password = ""
        if self.redis_password:
            password = f":{quote(self.redis_password, safe='')}@"
        return f"redis://{password}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    """获取配置单例（带缓存）。"""
    return Settings()


settings = get_settings()
