from .base_rpa import BaseRPA
from .rpa_manager import rpa_manager


class RPAFactory:
    """
    RPA 工厂类，负责统一实例化具体的 RPA 驱动和执行类。
    通过动态管理器 (BaseDynamicManager) 实现解耦。
    """

    @staticmethod
    def get_rpa(platform_name: str, config: dict) -> BaseRPA:
        """根据业务平台获取顶层 RPA 控制类"""
        cls = rpa_manager.get_rpa_class(platform_name)
        if cls:
            return cls(config)
        return None
