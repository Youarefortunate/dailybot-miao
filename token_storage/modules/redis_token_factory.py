import json
import redis
from typing import Optional, Any, Dict
from loguru import logger
from common.config import config


class RedisTokenFactory:
    """
    基于 Redis 的 Token 存储工厂
    利用 Redis Hash 结构天然规避多进程并发读写冲突
    """

    def __init__(
        self, host: str, port: int = 6379, password: Optional[str] = None, db: int = 0
    ):
        if not redis:
            raise ImportError(
                "缺少 redis 库，无法初始化 RedisTokenFactory，请运行 pip install redis"
            )
        self.host = host
        self.port = port
        self.db = db
        self.client = redis.Redis(
            host=host, port=port, password=password, db=db, decode_responses=True
        )
        # Redis Key 的基础前缀
        self.key_prefix = "dailybot:tokens"

    def get_platform_key(self, platform: str) -> str:
        """生成特定平台的 Redis Key，如 dailybot:tokens:feishu"""
        return f"{self.key_prefix}:{platform.lower()}"

    def get_platform_data(self, platform: str) -> Dict[str, Any]:
        """获取指定平台下的所有 Token 数据"""
        try:
            platform_key = self.get_platform_key(platform)
            # 通过 HGETALL 获取平台下的所有 open_id 及其序列化后的凭据
            raw_data = self.client.hgetall(platform_key)
            result = {}
            for k, v in raw_data.items():
                try:
                    result[k] = json.loads(v)
                except json.JSONDecodeError:
                    pass
            return result
        except Exception as e:
            logger.error(f"从 Redis 加载平台 {platform} 的 Token 失败: {e}")
            return {}

    async def set_platform_entry(self, platform: str, key: str, value: Any):
        """设置某个平台的单条用户条目"""
        # 拦截机制：只有在 config.ENABLED_WORKFLOWS 中的平台才允许写入 Redis 本地存储，其余被过滤
        enabled_workflows = getattr(config, "ENABLED_WORKFLOWS", [])
        platform_key_lower = platform.lower()

        if platform_key_lower not in enabled_workflows:
            logger.debug(
                f"平台 {platform} 未启用，已拒绝向 Redis {self.get_platform_key(platform)} 写入数据。"
            )
            return

        try:
            platform_key = self.get_platform_key(platform)
            # 序列化单条数据并使用 HSET 覆盖/更新单个用户的 Token 记录
            self.client.hset(platform_key, key, json.dumps(value, ensure_ascii=False))
        except Exception as e:
            logger.error(f"向 Redis 存入平台 {platform} 的 Token 失败: {e}")

    def get_all(self) -> Dict[str, Any]:
        """获取全平台缓存的数据，在 Redis 场景下该全量拉取可能会较慢，一般只由监控脚本使用"""
        try:
            result = {}
            enabled_workflows = getattr(config, "ENABLED_WORKFLOWS", [])
            for platform in enabled_workflows:
                result[platform] = self.get_platform_data(platform)
            return result
        except Exception as e:
            logger.error(f"从 Redis 获取全量 Token 失败: {e}")
            return {}
