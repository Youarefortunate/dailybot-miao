from common.config import config
from ..modules.base_platform import BasePlatform


class GLMAIPlatform(BasePlatform):
    """
    智谱 GLM 大模型平台接口实现 (兼容火山引擎 Ark 部署)
    """

    PLATFORM_NAME = "glm"
    # 这里我们匹配火山引擎的 URL 模式，因为用户提供的 BASE_URL 是火山引擎的
    URL_PATTERN = r"ark\.cn-beijing\.volces\.com"

    def __init__(self, config_dict=None):
        if config_dict is None:
            config_dict = {}
        config_dict.setdefault("name", "glm")
        config_dict.setdefault("baseURL", config.GLM_BASE_URL)
        super().__init__(config_dict)
        # GLM API 响应结构通常与 OpenAI 兼容，没有统一的 code/data 包裹层
        self.response_template = {"code": None, "data": None, "message": "message"}

    def get_token(self, params=None):
        """获取 GLM API Key"""
        if self.token:
            return self.token
        return config.GLM_API_KEY

    def set_request_interceptors(self, config_dict):
        """GLM 平台拦截器：使用 Bearer Token 认证"""
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
        """判断 Token 是否失效 (通常返回 401)"""
        return response.status_code == 401
