from abc import ABC, abstractmethod
from .ai_manager import ai_manager


class BaseAIProvider(ABC):
    """
    AI 供应商基类，定义大模型总结功能的规范
    """

    AI_PROVIDER_NAME = "unknown"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.AI_PROVIDER_NAME != "unknown":
            ai_manager.register_ai(cls.AI_PROVIDER_NAME, cls)

    @abstractmethod
    async def summarize(self, text: str) -> str:
        """
        根据供应商特定的逻辑（Prompt、参数等）执行文本总结
        """
        pass
