from abc import ABC, abstractmethod
from typing import List
from .models import CamouflageItem
from .camouflage_manager import camouflage_manager


class BaseCamouflage(ABC):
    """
    基础伪装素材提供者父类
    """

    SOURCE_NAME = "unknown"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 自动注册子类到全局伪装管理器
        if cls.SOURCE_NAME != "unknown":
            camouflage_manager.register(cls.SOURCE_NAME, cls)

    @abstractmethod
    async def fetch_items(self, since: str, until: str) -> List[CamouflageItem]:
        """
        获取指定日期范围内的素材记录
        """
        pass
