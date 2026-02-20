from loguru import logger
from common.config import config
from ..modules.base_platform import BasePlatform


class GeminiPlatform(BasePlatform):
    """
    Google Gemini 平台专用实现
    """

    PLATFORM_NAME = "gemini"
    URL_PATTERN = r"generativelanguage\.googleapis\.com"

    def __init__(self, cfg=None):
        if cfg is None:
            cfg = {}

        cfg.setdefault("name", "gemini")
        cfg.setdefault("baseURL", getattr(config, "GEMINI_BASE_URL", ""))

        super().__init__(cfg)
        # 获取认证 API Key
        self.api_key = cfg.get("api_key") or getattr(config, "GEMINI_API_KEY", None)
        # Gemini 报错通常在 error.message 下
        self.response_template = {
            "code": None,
            "data": None,
            "message": "error.message",
        }

    async def get_token(self, params=None):
        """Gemini 使用 API Key 认证，不使用 Bearer Token"""
        return None

    async def set_request_interceptors(self, config):
        """
        Gemini 专用请求拦截器：注入 x-goog-api-key 并清理 Authorization
        """
        if "headers" not in config:
            config["headers"] = {}

        # 优先使用实例初始化时的 api_key
        api_key = self.api_key or config.get("api_key")

        if api_key:
            config["headers"]["x-goog-api-key"] = api_key

        # 确保强制清理 Authorization 头部，确保不干扰 Google API
        config["headers"].pop("Authorization", None)
        # 设置通用请求头
        config["headers"].update(self.get_request_headers())

        return config

    async def _is_token_expired(self, response):
        """Gemini 使用 API Key，通常不涉及 Token 过期重试"""
        return False
