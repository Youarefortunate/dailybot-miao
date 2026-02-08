from .. import create_http_request
from ..platforms.modules.platform_manager import platform_manager
from config import config

# 创建默认的 HTTP 请求实例
request = create_http_request()


def setup_request(options=None, cb=None):
    """
    请求设置函数
    设置平台、基础 URL 等，支持多平台配置。
    """
    if options is None:
        options = {}

    # 默认值完全从全局 config 中获取
    platform_name = options.get("platform", config.DEFAULT_PLATFORM)
    base_url = options.get("baseURL", config.DEFAULT_BASE_URL)

    # 将 base_url 注入 options 中供平台初始化使用
    options["baseURL"] = base_url

    # 创建平台实例
    platform_instance = platform_manager.create_platform(platform_name, options)

    if not platform_instance:
        raise ValueError(f"Unsupported platform: {platform_name}")

    # 使用平台实例配置请求
    platform_instance.setup_request(request)

    # 执行回调函数
    if callable(cb):
        cb(request)

    return request
