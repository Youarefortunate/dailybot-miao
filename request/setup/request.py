from .. import create_http_request
from ..platforms.modules.platform_manager import platform_manager

# 创建默认的 HTTP 请求实例
request = create_http_request()

def setup_request(config=None, cb=None):
    """
    请求设置函数
    设置基础 URL、请求拦截器、响应拦截器等，支持多平台配置。
    """
    if config is None:
        config = {}
        
    platform = config.get('platform', 'feishu') # 默认飞书
    base_url = config.get('baseURL')
    token = config.get('token')
    url = config.get('url')

    # 根据 URL 检测平台，或使用指定的平台
    platform_name = platform
    if url:
        detected_platform = platform_manager.detect_platform(url)
        if detected_platform:
            platform_name = detected_platform

    # 创建平台实例，Token 现在由各平台类自行管理（如从 token_store 获取）
    platform_instance = platform_manager.create_platform(platform_name, config)

    if not platform_instance:
        raise ValueError(f"Unsupported platform: {platform_name}")

    # 使用平台实例配置请求
    platform_instance.setup_request(request)

    # 执行回调函数
    if callable(cb):
        cb(request)

    return request
