from loguru import logger
from api import apis
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

    def __init__(self, config=None):
        if config is None:
            config = {}
        config.setdefault("name", "feishu")
        config.setdefault("baseURL", "https://open.feishu.cn")
        super().__init__(config)
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

    def get_auth_header(self, token):
        return f"Bearer {token}"

    def get_request_headers(self):
        headers = super().get_request_headers()
        headers.update({"Content-Type": "application/json; charset=utf-8"})
        return headers
