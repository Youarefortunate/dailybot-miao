import lark_oapi as lark
from abc import ABC, abstractmethod
from typing import Any, Optional
from .sdk_adapter_manager import sdk_adapter_manager


class BaseSDKAdapter(ABC):
    """
    SDK 适配器基类
    """

    SDK_ADAPTER_NAME = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 自动将子类注册到适配器管理器
        if cls.SDK_ADAPTER_NAME:
            sdk_adapter_manager.register_adapter(cls.SDK_ADAPTER_NAME, cls)

    def __init__(self, config=None):
        self.config = config or {}
        self.client: Optional[lark.Client] = None

    @abstractmethod
    def init_sdk(self):
        """
        初始化平台官方 SDK 客户端
        """
        pass
