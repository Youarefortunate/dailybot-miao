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
    自动加载 modules 目录下的所有 API 模块
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    modules_dir = os.path.join(current_dir, 'modules')
    
    if os.path.exists(modules_dir):
        # 使用 pkgutil 扫描模块
        for _, name, is_pkg in pkgutil.iter_modules([modules_dir]):
            if not is_pkg:
                # 动态导入模块
                # 注意：__package__ 在这里应该是 'api'
                module = importlib.import_module(f".modules.{name}", __package__ or 'api')
                
                # 寻找模块中的定义。约定：
                # 1. 优先寻找命名为 get_{name}_api 的函数
                # 2. 其次寻找命名为 api_definition 的变量
                definition = None
                func_name = f"get_{name}_api"
                if hasattr(module, func_name):
                    definition = getattr(module, func_name)()
                elif hasattr(module, 'api_definition'):
                    definition = module.api_definition
                
                if definition:
                    # 注册到 api_register
                    api_register.define(name, definition)
                    Apis[name] = definition

# 执行加载
_load_modules()

# 导出生成的 API 对象
apis = api_register.apis

def setup_api_requester(instance):
    """
    设置 API 请求器实例
    """
    api_register.set_request(instance)

__all__ = ['api_register', 'apis', 'Apis', 'setup_api_requester']
