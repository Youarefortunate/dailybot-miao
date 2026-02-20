import os
from loguru import logger
from utils.dynamic_manager import BaseDynamicManager


class TokenStorageManager(BaseDynamicManager):
    """
    Token 存储管理器
    继承自 BaseDynamicManager，负责动态发现和扫描适配器实现
    """

    def __init__(self):
        # 确定 token_storage/impl 目录的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        impl_dir = os.path.join(os.path.dirname(current_dir), "impl")

        super().__init__(
            impl_dir_path=impl_dir,
            module_prefix="token_storage.impl",
            name_templates=["{key}_token_storage", "{key}"],
        )
        self._instances = {}

    def get_storage_instance(self, platform: str, factory=None):
        """
        获取指定平台的存储单例
        :param platform: 平台名称 (如 feishu)
        :param factory: 可选的 FileTokenFactory 实例
        """
        platform_name = platform.lower()
        if platform_name in self._instances:
            return self._instances[platform_name]

        platform_class = self.get_class(platform_name)
        if platform_class:
            # 获取初始化数据 (如果工厂存在)
            initial_data = factory.get_platform_data(platform_name) if factory else {}
            # 实例化
            instance = platform_class(data=initial_data)
            # 注入工厂
            if factory:
                instance.factory = factory

            self._instances[platform_name] = instance
            return instance

        return None


# 导出全局管理器单例
token_storage_manager = TokenStorageManager()
