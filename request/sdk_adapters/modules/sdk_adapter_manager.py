import os
from loguru import logger
from utils.dynamic_manager import BaseDynamicManager


class SDKAdapterManager(BaseDynamicManager):
    """
    SDK 适配器管理器
    支持动态发现和自动注册适配器子类
    """

    def __init__(self):
        # 确定 impl 目录的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        impl_dir = os.path.join(os.path.dirname(current_dir), "impl")

        # 初始化基类
        super().__init__(
            impl_dir_path=impl_dir,
            module_prefix="request.sdk_adapters.impl",
            name_templates=["{key}_sdk_adapter", "{key}"],
        )

    def register_adapter(self, name, adapter_class):
        """
        供 BaseSDKAdapter.__init_subclass__ 调用的注册方法
        """
        self.register(name, adapter_class)

    def get_adapter_class(self, name):
        """
        获取适配器类
        """
        return self.get_class(name)

    def create_adapter(self, adapter_name, config=None):
        """
        创建适配器实例
        """
        adapter_class = self.get_adapter_class(adapter_name)
        if not adapter_class:
            return None
        return adapter_class(config)


sdk_adapter_manager = SDKAdapterManager()
