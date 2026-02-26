import os
from utils.dynamic_manager import BaseDynamicManager


class RPAManager(BaseDynamicManager):
    """RPA 平台业务层动态管理器"""

    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        impl_dir = os.path.join(os.path.dirname(current_dir), "impl")

        super().__init__(
            impl_dir_path=impl_dir,
            module_prefix="rpa.impl",
            name_templates=["{key}_rpa", "{key}"],
        )

    def register_rpa(self, name: str, rpa_class):
        self.register(name, rpa_class)

    def get_rpa_class(self, name: str):
        return self.get_class(name)

    @BaseDynamicManager.ensure_discovery
    def get_registered_platforms(self):
        return self.get_all_keys()


rpa_manager = RPAManager()
