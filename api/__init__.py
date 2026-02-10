import os
import importlib
import pkgutil
from request import create_api_register

# 创建 API 注册器实例
api_register = create_api_register()

# 存储原始配置的字典
Apis = {}


def _load_modules():
    """
    自动加载 modules 目录下的所有 API 模块，支持递归子目录
    获取的规则是：父文件名 + 子文件名 (例如 feishu/app/auth.py -> feishu_app_auth)
    使用时：apis.feishu_app_auth.get_token
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    modules_dir = os.path.join(current_dir, "modules")

    if not os.path.exists(modules_dir):
        return

    # 递归遍历目录
    for root, dirs, files in os.walk(modules_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                # 获取文件的相对路径并转换为模块路径
                rel_path = os.path.relpath(os.path.join(root, file), modules_dir)
                module_parts = rel_path[:-3].replace(os.sep, ".").split(".")

                # 生成注册名: 父目录名 + 子模块名
                api_name = "_".join(module_parts)

                # 拼接完整的导入路径
                module_path = f".modules.{'.'.join(module_parts)}"

                try:
                    # 动态导入模块
                    module = importlib.import_module(module_path, __package__ or "api")

                    # 寻找模块中的定义
                    definition = None
                    # 尝试多种可能的获取函数名: get_{last_part}_api
                    last_part = module_parts[-1]
                    func_name = f"get_{last_part}_api"

                    if hasattr(module, func_name):
                        definition = getattr(module, func_name)()
                    elif hasattr(module, "api_definition"):
                        definition = module.api_definition

                    if definition:
                        # 注册到 api_register
                        api_register.define(api_name, definition)
                        Apis[api_name] = definition
                except Exception as e:
                    print(f"Error loading module {module_path}: {e}")


# 执行加载
_load_modules()

# 导出生成的 API 对象
apis = api_register.apis


def setup_api_requester(instance):
    """
    设置 API 请求器实例
    """
    api_register.set_request(instance)


__all__ = ["api_register", "apis", "Apis", "setup_api_requester"]
