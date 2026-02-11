from loguru import logger
from api import apis
from config import config
from ..modules.base_platform import BasePlatform
from token_store import (
    get_refresh_token,
    save_token,
    get_token as get_local_token,
    get_app_token,
    fetch_tenant_access_token,
    refresh_user_token as store_refresh_user_token,
    get_current_open_id,
)
from ...hooks.use_request import use_request


class FeishuPlatform(BasePlatform):
    """
    飞书平台接口实现
    """

    PLATFORM_NAME = "feishu"
    URL_PATTERN = r"feishu\.cn"

    def __init__(self, config_dict=None):
        if config_dict is None:
            config_dict = {}
        config_dict.setdefault("name", "feishu")
        config_dict.setdefault("baseURL", config.FEISHU_BASE_URL)
        super().__init__(config_dict)
        # 飞书特有的响应结构: code, data, msg
        self.response_template = {"code": "code", "data": "data", "message": "msg"}

    def get_token(self, params=None):
        """
        自动获取 Token。
        - 如果 params 中包含 auth_type="app"，则返回自建应用 Token。
        - 否则默认返回用户 access_token。
        """
        if self.token:
            return self.token

        open_id = get_current_open_id()
        if not open_id:
            return None

        if isinstance(params, dict) and params.get("auth_type") == "app":
            return get_app_token(open_id)
        return get_local_token(open_id)

    def _is_token_expired(self, response):
        """
        判断飞书 Token 是否过期或无效
        """
        # 1. 检查 HTTP 状态码
        if response.status_code == 401:
            return True

        # 2. 检查业务错误码
        try:
            data = response.json()
            code = data.get("code")
            msg = data.get("msg", "").lower()

            # 99991677: Token 过期
            # 99991661: Token 无效或未提供
            if code in [99991677, 99991661]:
                return True

            # 关键词匹配
            if "token expired" in msg or "invalid access token" in msg:
                return True
        except:
            pass
        return False

    def refresh_token(self, params=None):
        """
        执行无感刷新：完全自闭环，使用 token_store 中封装的逻辑。
        """
        open_id = get_current_open_id()
        if not open_id:
            logger.warning("[Feishu] 刷新失败：未找到当前用户 open_id")
            return None

        logger.info(f"[Feishu] 正在为 {open_id} 进行自闭环无感刷新 (token_store)...")

        refresh_tk = get_refresh_token(open_id)
        if not refresh_tk:
            logger.warning("[Feishu] 刷新失败：未找到有效 refresh_token")
            return None

        try:
            # 直接调用封装好的刷新逻辑
            new_token = store_refresh_user_token(open_id, refresh_tk)
            if new_token:
                logger.info("[Feishu] 自闭环刷新成功 (token_store)")
                return new_token
        except Exception as e:
            logger.error(f"[Feishu] 刷新过程中出现异常: {e}")

        return None

    # 飞书常见风控/被标记错误码映射
    BLOCKED_CODES = {
        230001: "机器人被飞书禁用或移出群聊",
        230002: "机器人不在目标群聊中",
        230003: "发送消息触发飞书风控策略",
        230006: "目标群聊已被解散",
        230014: "机器人发送消息频率受限",
        230020: "机器人被群管理员禁言",
        230099: "机器人发送消息被飞书安全策略拦截",
    }

    def set_response_interceptors(self, response, config, http_request):
        """
        飞书响应拦截器：在基类逻辑基础上，增加对飞书业务错误码的检测。
        飞书 API 即使出现业务错误也可能返回 HTTP 200，需要额外检查 JSON body 中的 code 字段。
        """
        response.response_template = self.response_template

        # 1. 先检测 Token 过期
        if self._is_token_expired(response):
            logger.warning(f"[{self.PLATFORM_NAME}] 检测到 Token 过期，尝试自动刷新...")
            auth_params = (
                config.get("params", {})
                if config.get("method") == "GET"
                else config.get("json", {})
            )
            new_token = self.refresh_token(auth_params)
            if new_token:
                logger.info(
                    f"[{self.PLATFORM_NAME}] Token 刷新成功，正在重新发起原始请求..."
                )
                return http_request.request(config)

        # 2. 处理 HTTP 非 2xx 错误
        if not (200 <= response.status_code < 300):
            raise self.create_error(
                response.status_code, self._parse_error_data(response)
            )

        # 3. 检测飞书业务错误码（HTTP 200 但 code != 0 的情况）
        try:
            data = response.json()
            code = data.get("code")
            msg = data.get("msg", "") or data.get("message", "")

            if code and code != 0:
                # 检查是否为风控/被标记类错误
                blocked_reason = self.BLOCKED_CODES.get(code)
                if blocked_reason:
                    logger.error(
                        f"[{self.PLATFORM_NAME}] 🚫 {blocked_reason} (code={code}, msg={msg})"
                    )
                    raise self.create_error(
                        code, {"msg": blocked_reason, "code": code, "raw_msg": msg}
                    )
        except ValueError:
            # JSON 解析失败，忽略
            pass

        return response

    def get_auth_header(self, token):
        return f"Bearer {token}"

    def get_request_headers(self):
        headers = super().get_request_headers()
        headers.update({"Content-Type": "application/json; charset=utf-8"})
        return headers

    def set_error_interceptors(self, error, config, http_request):
        """
        飞书错误拦截器：检测连接层异常。
        飞书风控的典型表现是请求发出后服务端直接断开连接、不返回任何响应。
        """
        error_msg = str(error).lower()

        # 连接被远端关闭（飞书风控的典型表现）
        connection_blocked_keywords = [
            "remotedisconnected",
            "remote end closed connection",
            "connection aborted",
            "connection refused",
            "connection reset",
        ]

        is_blocked = any(kw in error_msg for kw in connection_blocked_keywords)
        if is_blocked:
            blocked_error = Exception(f"飞书服务器拒绝响应，可能已被风控标记: {error}")
            blocked_error.platform = self.PLATFORM_NAME
            blocked_error.original_error = error
            raise blocked_error

        raise error
