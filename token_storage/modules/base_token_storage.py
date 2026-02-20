from typing import Optional, Any, Dict
from .token_storage_manager import token_storage_manager


class BaseTokenStorage:
    """
    Token 存储基类
    通过 __init_subclass__ 实现自动注册到管理器
    """

    STORAGE_PLATFORM_NAME = "unknown"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.STORAGE_PLATFORM_NAME != "unknown":
            token_storage_manager.register(cls.STORAGE_PLATFORM_NAME, cls)

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data = data or {}
        self.factory = None  # 延迟注入工厂实现持久化

    async def get_token(
        self, identifier: Optional[str] = None, **kwargs
    ) -> Optional[str]:
        """获取访问令牌 (Access Token)，供子类重写。identifier用于区分用户，应用级可传None"""
        raise NotImplementedError

    async def get_app_token(
        self, identifier: Optional[str] = None, **kwargs
    ) -> Optional[str]:
        """
        获取应用令牌 (App Token)
        仅在有严格应用级隔离的平台（如飞书）中重写，无此特性的平台将默认返回 None
        """
        return None

    async def refresh_token(
        self, identifier: Optional[str] = None, **kwargs
    ) -> Optional[str]:
        """
        无感刷新令牌
        不具备刷新机制的平台默认返回 None
        """
        return None

    async def save_token(self, identifier: str, **kwargs):
        """
        保存令牌及其关联数据
        不同平台的 Token 结构不同（如有效期、刷新令牌）。统一定义为 kwargs 让子类解析。
        """
        raise NotImplementedError
