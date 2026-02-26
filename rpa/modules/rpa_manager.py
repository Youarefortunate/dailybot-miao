import os
from utils.dynamic_manager import BaseDynamicManager

# 平台 RPA 实现所在目录
_IMPL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "impl"))


class RPAManager(BaseDynamicManager):
    """RPA 平台业务层动态管理器"""

    def __init__(self):
        super().__init__(
            impl_dir_path=_IMPL_DIR,
            module_prefix="rpa.impl",
            name_templates=["{key}_rpa"],
        )


rpa_manager = RPAManager()
