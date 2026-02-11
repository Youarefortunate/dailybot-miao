import os
from utils.dynamic_manager import BaseDynamicManager


class AIManager(BaseDynamicManager):
    """
    AI 供应商管理器，动态发现服务
    """

    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # providers/impl
        impl_dir = os.path.join(os.path.dirname(current_dir), "impl")

        super().__init__(
            impl_dir_path=impl_dir,
            module_prefix="providers.impl",
            name_templates=["{key}_ai", "{key}"],
        )

    def register_ai(self, name: str, ai_class):
        self.register(name, ai_class)

    def get_ai_class(self, name: str):
        return self.get_class(name)

    @BaseDynamicManager.ensure_discovery
    def get_all_ai_providers(self):
        return self.get_all_keys()


ai_manager = AIManager()
