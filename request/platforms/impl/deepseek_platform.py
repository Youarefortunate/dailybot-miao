from common.config import config
from ..modules.base_platform import BasePlatform


class DeepSeekAIPlatform(BasePlatform):
    """
    DeepSeek AI 大模型平台接口实现 (由于使用火山引擎，其逻辑与 GLM/豆包 类似)
    """

    PLATFORM_NAME = "deepseek"
    URL_PATTERN = r"ark\.cn-beijing\.volces\.com"

    def __init__(self, config_dict=None):
        if config_dict is None:
            config_dict = {}
        config_dict.setdefault("name", "deepseek")
        config_dict.setdefault("baseURL", config.DEEPSEEK_BASE_URL)
        super().__init__(config_dict)
        # DeepSeek API 兼容 OpenAI，没有统一的 code/data 包裹层
        self.response_template = {"code": None, "data": None, "message": "message"}

    def get_token(self, params=None):
        """获取 DeepSeek API Key"""
        if self.token:
            return self.token
        return config.DEEPSEEK_API_KEY

    def set_request_interceptors(self, config_dict):
        """DeepSeek 平台拦截器：使用 Bearer Token 认证"""
        token = self.get_token()
        if token:
            if "headers" not in config_dict:
                config_dict["headers"] = {}
            config_dict["headers"]["Authorization"] = f"Bearer {token}"

        # 设置通用头
        headers = self.get_request_headers()
        if "headers" not in config_dict:
            config_dict["headers"] = {}
        config_dict["headers"].update(headers)
        return config_dict

    def _is_token_expired(self, response):
        """判断 Token 是否失效"""
        return response.status_code == 401
