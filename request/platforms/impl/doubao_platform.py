from config import config
from ..modules.base_platform import BasePlatform


class DoubaoAIPlatform(BasePlatform):
    """
    豆包大模型平台接口实现
    """

    PLATFORM_NAME = "doubao"
    URL_PATTERN = r"ark\.cn-beijing\.volces\.com"

    def __init__(self, config_dict=None):
        if config_dict is None:
            config_dict = {}
        config_dict.setdefault("name", "doubao")
        config_dict.setdefault("baseURL", config.DOUBAO_BASE_URL)
        super().__init__(config_dict)
        # 豆包 API 响应没有统一的 code/data 包裹层，直接返回整个响应体
        self.response_template = {"code": None, "data": None, "message": "message"}

    def get_token(self, params=None):
        """获取豆包 API Key"""
        if self.token:
            return self.token
        return config.DOUBAO_API_KEY

    def set_request_interceptors(self, config_dict):
        """豆包平台拦截器：使用 Bearer Token 认证"""
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
        """判断豆包 Token 是否失效 (通常返回 401)"""
        return response.status_code == 401
