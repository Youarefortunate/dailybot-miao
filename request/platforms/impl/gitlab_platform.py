from loguru import logger
from common.config import config
from ..modules.base_platform import BasePlatform


class GitlabPlatform(BasePlatform):
    """
    GitLab 平台接口实现
    """

    PLATFORM_NAME = "gitlab"
    # 匹配 git.b2bwings.com 域名
    URL_PATTERN = r"git\.b2bwings\.com"

    def __init__(self, config_dict=None):
        if config_dict is None:
            config_dict = {}
        config_dict.setdefault("name", "gitlab")
        # 默认使用配置中的 GitLab Base URL 并拼接 API v4
        config_dict.setdefault(
            "baseURL", f"{config.GITLAB_BASE_URL.rstrip('/')}/api/v4"
        )
        super().__init__(config_dict)
        # GitLab API 响应通常直接是数据，没有统一的 code/msg/data 包裹层
        # 根据使用习惯，我们设置数据层为 None 表示返回整个响应体
        self.response_template = {"code": "id", "data": None, "message": "message"}

    async def get_token(self, params=None):
        """
        获取 GitLab Access Token
        """
        if self.token:
            return self.token
        return config.GITLAB_TOKEN

    async def set_request_interceptors(self, config_dict):
        """
        GitLab 特有拦截器：使用 Private-Token 认证
        """
        token = await self.get_token()
        if token:
            if "headers" not in config_dict:
                config_dict["headers"] = {}
            # GitLab 常见认证方式使用 Private-Token 请求头
            config_dict["headers"]["Private-Token"] = token

        # 设置通用头
        headers = self.get_request_headers()
        if "headers" not in config_dict:
            config_dict["headers"] = {}
        config_dict["headers"].update(headers)
        return config_dict

    async def _is_token_expired(self, response):
        """
        判断 GitLab Token 是否失效 (通常返回 401)
        """
        return response.status_code == 401
