import os
from utils.dynamic_manager import BaseDynamicManager


class WorkflowManager(BaseDynamicManager):
    """
    工作流管理器，动态加载 workflows/impl 目录下的插件
    """

    def __init__(self):
        # workflows/impl
        impl_dir = os.path.join("workflows", "impl")

        super().__init__(
            impl_dir_path=impl_dir,
            module_prefix="workflows.impl",
            name_templates=["{key}_workflow", "{key}"],
        )

    def register_workflow(self, name: str, workflow_class):
        self.register(name, workflow_class)

    def get_workflow_class(self, name: str):
        return self.get_class(name)

    @BaseDynamicManager.ensure_discovery
    def get_all_workflow_names(self):
        return self.get_all_keys()


workflow_manager = WorkflowManager()
