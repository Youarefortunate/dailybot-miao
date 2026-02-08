import os
import importlib
import pkgutil
import re

class PlatformManager:
    """
    平台管理器
    支持动态发现和自动注册平台子类
    """
    def __init__(self):
        self.platforms = {}
        self.url_patterns = {}
        self._discovered = False

    def register_platform(self, name, platform_class):
        """
        供 BasePlatform.__init_subclass__ 调用的注册方法
        """
        self.platforms[name.lower()] = platform_class

    def register_url_pattern(self, name, pattern):
        """
        注册 URL 匹配规则，支持正则字符串
        """
        self.url_patterns[name.lower()] = pattern

    def _ensure_discovered(self):
        """
        确保 impl 目录下的所有平台类已被加载
        """
        if self._discovered:
            return
            
        # 动态加载 impl 目录下的所有模块
        # 获取 impl 目录的绝对路径
        try:
            # 找到 impl 目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            impl_dir = os.path.join(os.path.dirname(current_dir), 'impl')
            
            if os.path.exists(impl_dir):
                # 遍历 impl 目录下的所有 .py 文件
                for _, name, is_pkg in pkgutil.iter_modules([impl_dir]):
                    if not is_pkg:
                        # 动态导入模块，这将触发 BasePlatform.__init_subclass__
                        # 使用 ...impl 从 platforms.modules 向上找两级到 request，再进入 platforms.impl
                        importlib.import_module(f"...impl.{name}", __name__)
            
            self._discovered = True
        except Exception as e:
            print(f"Platform discovery error: {e}")

    def get_platform_class(self, name):
        self._ensure_discovered()
        return self.platforms.get(name.lower())

    def detect_platform(self, url):
        self._ensure_discovered()
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
        self._ensure_discovered()
        platform_class = self.get_platform_class(platform_name)
        if not platform_class:
            return None
        return platform_class(config)

    def get_registered_platforms(self):
        self._ensure_discovered()
        return list(self.platforms.keys())

platform_manager = PlatformManager()
