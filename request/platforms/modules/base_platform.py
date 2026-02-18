from loguru import logger
from exceptions.result import Result
from enums.result_code import ResultCode


class BasePlatform:
    """
    平台基类
    """

    PLATFORM_NAME = "unknown"
    URL_PATTERN = None  # 支持正则或字符串
    MAX_RETRY_LIMIT = 2

    def __init__(self, config=None):
        if config is None:
            config = {}
        self.name = config.get("name", "Unknown")
        self.base_url = config.get("baseURL", "")
        self.token = config.get("token")
        self.hostname = config.get("hostname", "")
        # 默认响应结构映射
        self.response_template = {"code": "code", "data": "data", "message": "message"}
        # Token 刷新重试计数器
        self._retry_count = 0

    def get_name(self):
        return self.name

    def get_base_url(self):
        return self.base_url

    def get_token(self, params=None):
        """获取 Token，子类需实现具体的凭证获取逻辑"""
        return self.token

    def refresh_token(self, params=None):
        """重新获取/刷新 Token，子类需实现"""
        return None

    def set_request_interceptors(self, config):
        """
        请求拦截器：自动注入 Auth Header
        """
        if "headers" not in config:
            config["headers"] = {}

        # 请求头添加token
        if "Authorization" not in config["headers"]:
            token = self.get_token(params=config)
            if token:
                # 设置认证头
                auth_header = self.get_auth_header(token)
                if auth_header:
                    config["headers"]["Authorization"] = auth_header

        # 设置平台特定的通用请求头
        headers = self.get_request_headers()
        if "headers" not in config:
            config["headers"] = {}
        config["headers"].update(headers)
        return config

    def get_auth_header(self, token):
        """构造认证头字符串，如 'Bearer {token}'"""
        return f"Bearer {token}"

    def get_request_headers(self):
        return {
            "Connection": "close",  # FIX: requests库会可能存在："Remote end closed connection without response" 的解决方案
            "User-Agent": "MCP-Audit-Client/1.0",
        }

    def set_response_interceptors(self, response, config, http_request):
        """
        响应拦截器：处理成功响应，并检测 Token 过期触发重试逻辑
        """
        response.response_template = self.response_template

        # 1. 检测 Token 过期 (身份认证类错误)
        if self._is_token_expired(response):
            # 增加死循环保护逻辑
            if self._retry_count >= self.MAX_RETRY_LIMIT:
                logger.error(
                    f"[{self.PLATFORM_NAME}] Token 刷新后重试仍失败，已达到最大重试次数 ({self.MAX_RETRY_LIMIT})，防止进入死循环。"
                )
                self._retry_count = 0  # 熔断导出前归零
                return response

            logger.warning(
                f"[{self.PLATFORM_NAME}] 检测到 Token 过期，尝试自动刷新 (第 {self._retry_count + 1} 次尝试)..."
            )

            # 执行刷新逻辑
            # 直接传递完整的请求配置对象 config，以便平台实现（如 FeishuPlatform）能够获取所有上下文标识（如 auth_type）
            self._retry_count += 1
            new_token = self.refresh_token(config)

            if new_token:
                logger.info(
                    f"[{self.PLATFORM_NAME}] Token 刷新成功，直接注入新 Token 并重新发起原始请求..."
                )

                # 直接在 config 中设置最新的 Authorization 头，确确保重试请求直接通过
                if "headers" not in config:
                    config["headers"] = {}
                config["headers"]["Authorization"] = self.get_auth_header(new_token)

                # 递归重试
                return http_request.request(config)
            else:
                # 如果刷新本身失败，也需要归零以便下次全新请求开始
                self._retry_count = 0

        # 2. 如果请求成功或遇到非 401 错误，重置计数器
        self._retry_count = 0

        # 2. 处理常规响应
        if 200 <= response.status_code < 300:
            # 尝试根据模板解析为 Result 对象
            try:
                # 检查响应内容类型，非 JSON 直接包装
                if "application/json" not in response.headers.get("Content-Type", ""):
                    return Result.success(data=response.text)

                raw_data = response.json()

                # 如果 raw_data 是列表（如 GitLab Commits），直接作为数据返回
                if isinstance(raw_data, list):
                    return Result.success(data=raw_data)

                # 如果不是字典，直接转换
                if not isinstance(raw_data, dict):
                    return Result.success(data=raw_data)

                # 获取目标字段名并提取数据
                code_key = self.response_template.get("code")
                data_key = self.response_template.get("data")
                msg_key = self.response_template.get("message", "message")

                # 提取数据：优先从 data_key 获取，不存在则使用全量数据
                p_code = raw_data.get(code_key) if code_key else 0
                p_msg = raw_data.get(msg_key, "success") if msg_key else "success"

                if data_key and data_key in raw_data:
                    p_data = raw_data.get(data_key)
                else:
                    p_data = raw_data

                # 情况 A：业务逻辑成功
                if p_code in [0, 200, "0", None]:
                    return Result.success(data=p_data, msg=p_msg)
                # 情况 B：业务逻辑异常
                else:
                    return Result.fail(code=p_code, msg=p_msg, data=p_data)

            except Exception as e:
                logger.error(f"[{self.PLATFORM_NAME}] 响应解析失败: {e}")
                return Result.success(data=response.text)
        else:
            error_data = self._parse_error_data(response)
            raise self.create_error(response.status_code, error_data)

    def _is_token_expired(self, response):
        """子类需实现此方法来判断 Token 是否过期"""
        return False

    def _parse_error_data(self, response):
        try:
            if "application/json" in response.headers.get("Content-Type", ""):
                return response.json()
        except:
            pass
        return response.text

    def set_error_interceptors(self, error, config, http_request):
        # 简单处理 Python 异常到自定义错误的转换
        raise error

    def create_error(self, status, data):
        message_key = self.response_template.get("message", "message")
        code_key = self.response_template.get("code", "code")

        message = data.get(message_key) if isinstance(data, dict) else str(data)
        biz_code = data.get(code_key) if isinstance(data, dict) else status

        err = Exception(message or f"HTTP {status} Error")
        err.status = status
        err.biz_code = biz_code
        err.data = data
        err.platform = self.PLATFORM_NAME
        return err

    def setup_request(self, http_request):
        """
        设置平台相关的配置到 HttpRequest 实例
        """
        http_request.set_base_url(self.get_base_url())

        # 设置拦截器
        http_request.set_req_interceptors(
            lambda config: self.set_request_interceptors(config)
        )

        http_request.set_res_interceptors(
            lambda response, config: self.set_response_interceptors(
                response, config, http_request
            ),
            lambda error, config: self.set_error_interceptors(
                error, config, http_request
            ),
        )
