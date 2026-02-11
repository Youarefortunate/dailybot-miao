from .ai_manager import ai_manager


class AIFactory:
    """
    AI 供应商工厂
    """

    @staticmethod
    def get_ai(name: str):
        cls = ai_manager.get_ai_class(name)
        if not cls:
            return None
        return cls()
