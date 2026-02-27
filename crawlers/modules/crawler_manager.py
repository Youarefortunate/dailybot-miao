import os
from utils.dynamic_manager import BaseDynamicManager


class CrawlerManager(BaseDynamicManager):
    """
    爬虫管理器
    继承通用工具类，支持动态发现和自动注册爬虫子类
    """

    def __init__(self):
        # 确定 impl 目录相对于项目根目录的路径
        impl_dir = os.path.join("crawlers", "impl")

        # 初始化基类
        super().__init__(
            impl_dir_path=impl_dir,
            module_prefix="crawlers.impl",
            name_templates=["{key}_crawler", "{key}"],
        )

    def register_crawler(self, crawler_name: str, crawler_class):
        """
        注册爬虫类
        """
        self.register(crawler_name, crawler_class)

    def get_crawler_class(self, name: str):
        """
        获取爬虫类
        """
        return self.get_class(name)

    def get_registered_platforms(self) -> list:
        """
        获取所有已注册的平台名称
        """
        return self.get_all_keys()


# 单例
crawler_manager = CrawlerManager()
