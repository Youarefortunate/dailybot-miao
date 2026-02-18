import os
import re
from loguru import logger
from common.config import config
from utils.dynamic_manager import BaseDynamicManager
from .base_platform import BasePlatform
from .platform_factory import PlatformFactory


class PlatformManager(BaseDynamicManager):
    """
    平台管理器：采用主动扫描机制解耦 BasePlatform，支持动态专用平台与通用平台工厂。
    """

    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        super().__init__(
            impl_dir_path=os.path.join(os.path.dirname(current_dir), "impl"),
            module_prefix="request.platforms.impl",
            name_templates=["{key}_platform", "{key}"],
        )
        self.url_patterns = {}
        self._is_synced = False  # 懒加载同步状态

    def _sync_subclasses(self):
        """确保所有 BasePlatform 子类已注册到管理器"""
        if self._is_synced:
            return

        # 触发基类扫描并遍历子类实现主动注册
        self.ensure_fully_discovered()
        for cls in BasePlatform.__subclasses__():
            if (name := getattr(cls, "PLATFORM_NAME", "unknown")) != "unknown":
                self.register(name, cls)
                if pattern := getattr(cls, "URL_PATTERN", None):
                    self.url_patterns[name.lower()] = pattern

        self._is_synced = True

    def get_platform_class(self, name):
        """获取已注册的平台类"""
        self._sync_subclasses()
        return self.get_class(name)

    @BaseDynamicManager.ensure_discovery
    def detect_platform(self, url):
        """根据 URL 自动识别平台"""
        if not url:
            return None
        self._sync_subclasses()

        for name, pattern in self.url_patterns.items():
            if (isinstance(pattern, str) and re.search(pattern, url)) or (
                callable(pattern) and pattern(url)
            ):
                return name
        return None

    def create_platform(self, platform_name, config_override=None):
        """
        创建平台实例。
        优先查找已注册的专用子类，否则委托 PlatformFactory 生成通用实例。
        """
        if platform_class := self.get_platform_class(platform_name):
            return platform_class(config_override)

        # 降级到通用工厂
        return PlatformFactory.create(platform_name, config_override)

    def get_registered_platforms(self):
        """获取所有可用平台标识"""
        self._sync_subclasses()
        return self.get_all_keys()


platform_manager = PlatformManager()
