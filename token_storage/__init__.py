import threading
from loguru import logger
from common.config import config
from .modules.token_storage_manager import token_storage_manager
from .modules.file_token_factory import FileTokenFactory
from .modules.redis_token_factory import RedisTokenFactory
from .modules.base_token_storage import BaseTokenStorage

# 默认 Token 文件名
DEFAULT_TOKEN_FILE = "token.json"

# 全局工厂实例缓存（单例）与互斥锁
_token_factory = None
_factory_lock = threading.Lock()


def get_factory():
    """
    延迟初始化全局 Token 工厂（懒加载）。
    通过双重检查锁（DCL）确保多线程环境下单例的唯一性与降级逻辑的原子性。
    """
    global _token_factory
    if _token_factory is not None:
        return _token_factory

    with _factory_lock:
        # 二次检查，防止竞争
        if _token_factory is not None:
            return _token_factory

        redis_cfg = config.get("redis")
        selected_factory = None

        if redis_cfg and isinstance(redis_cfg, dict) and redis_cfg.get("host"):
            try:
                redis_host = redis_cfg.get("host")
                redis_port = redis_cfg.get("port", 6379)
                redis_password = redis_cfg.get("password")
                if not redis_password:
                    redis_password = None
                redis_db = redis_cfg.get("database", 0)

                # 先创建临时工厂，验证成功后再确认为全局唯一实例
                temp_factory = RedisTokenFactory(
                    host=redis_host,
                    port=int(redis_port),
                    password=redis_password,
                    db=int(redis_db),
                )
                temp_factory.client.ping()

                selected_factory = temp_factory
                auth_status = " (带认证)" if redis_password else " (无认证)"
                logger.info(
                    f"🟢 已启用 Redis 作为 Token 存储介质: {redis_host}:{redis_port}/{redis_db}{auth_status}"
                )
            except Exception as e:
                logger.error(
                    f"🔴 Redis 获取失败 (可能未启动或网络不通): {e}。将自动切换到文件存储。"
                )
                selected_factory = FileTokenFactory(DEFAULT_TOKEN_FILE)
        else:
            selected_factory = FileTokenFactory(DEFAULT_TOKEN_FILE)

        _token_factory = selected_factory
        return _token_factory


def get_platform_storage(platform: str) -> BaseTokenStorage:
    """
    获取指定平台的 Token 存储对象
    """
    return token_storage_manager.get_storage_instance(platform, factory=get_factory())


async def load_all_tokens():
    """
    加载所有 Token 数据
    """
    return get_factory().get_all()


__all__ = [
    "get_platform_storage",
    "load_all_tokens",
    "token_storage_manager",
    "BaseTokenStorage",
]
