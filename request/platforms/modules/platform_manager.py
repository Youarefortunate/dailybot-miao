import os
import re
from utils.dynamic_manager import BaseDynamicManager


class PlatformManager(BaseDynamicManager):
    """
    平台管理器
    支持动态发现和自动注册平台子类
    """

    def __init__(self):
        # 确定 impl 目录的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        impl_dir = os.path.join(os.path.dirname(current_dir), "impl")

        # 初始化基类
        # 注意：这里的前缀根据目录结构确定为 request.platforms.impl
        super().__init__(
            impl_dir_path=impl_dir,
            module_prefix="request.platforms.impl",
            name_templates=["{key}_platform", "{key}"],
        )

        # 平台特有的 URL 匹配规则
        self.url_patterns = {}

    def register_platform(self, name, platform_class):
        """
        供 BasePlatform.__init_subclass__ 调用的注册方法
        """
        self.register(name, platform_class)

    def register_url_pattern(self, name, pattern):
        """
        注册 URL 匹配规则，支持正则字符串
        """
        self.url_patterns[name.lower()] = pattern

    def get_platform_class(self, name):
        """
        获取平台类 (利用基类的三级查找策略)
        """
        return self.get_class(name)

    @BaseDynamicManager.ensure_discovery
    def detect_platform(self, url):
        """
        通过 URL 自动检测平台名称
        """
        if not url:
            return None
        for name, pattern in self.url_patterns.items():
            if isinstance(pattern, str):
                if re.search(pattern, url):
                    return name
            elif callable(pattern):
                if pattern(url):
                    return name
        return None

    def create_platform(self, platform_name, config=None):
        """
        创建平台实例
        """
        platform_class = self.get_platform_class(platform_name)
        if not platform_class:
            return None
        return platform_class(config)

    def get_registered_platforms(self):
        """
        获取所有已注册的平台
        """
        return self.get_all_keys()


platform_manager = PlatformManager()
