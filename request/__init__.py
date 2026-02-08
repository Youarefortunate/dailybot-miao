from .core.http_request import HttpRequest
from .core.api_register import ApiRegister

def create_api_register():
    """
    创建 ApiRegister 实例
    """
    return ApiRegister()

def create_http_request(config=None):
    """
    创建 HttpRequest 实例
    """
    return HttpRequest(config)
