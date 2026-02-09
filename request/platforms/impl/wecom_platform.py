import time
from api import apis
from ..modules.base_platform import BasePlatform
from ...hooks.use_request import use_request


# 简单的进程内缓存，用于存储企业微信 access_token 及过期时间
_WECOM_ACCESS_TOKEN = None
_WECOM_TOKEN_EXPIRES_AT = 0


class WecomPlatform(BasePlatform):
    """
    企业微信（WeCom）平台接口实现，支持自动获取与无感刷新 access_token。
    """

    # 平台内部名称，在 API 定义中可通过 "platform": "wecom" 来指定使用本平台
    PLATFORM_NAME = "wecom"
    # 通过 URL 自动识别企业微信开放平台域名
    URL_PATTERN = r"qyapi\.weixin\.qq\.com"

    def __init__(self, config=None):
        if config is None:
            config = {}

        # 默认平台名称和基础域名
        config.setdefault("name", "wecom")
        # 企业微信开放平台基础域名
        config.setdefault("baseURL", "https://qyapi.weixin.qq.com")

        super().__init__(config)

        # 企业微信 corp_id / corp_secret（建议通过 config 传入或在外部统一读取环境变量）
        self.corp_id = config.get("corp_id")
        self.corp_secret = config.get("corp_secret")

        # 企业微信通用响应结构:
        # {
        #   "errcode": 0,
        #   "errmsg": "ok",
        #   ... 业务字段 ...
        # }
        # 少量接口会额外包一层 data，这里兼容两种：
        # - 有 data 字段时，优先使用 data
        # - 没有 data 字段时，use_request 会返回整个 JSON
        self.response_template = {"code": "errcode", "data": "data", "message": "errmsg"}

    # ---------- Token 获取与无感刷新 ----------

    def _get_cached_token(self):
        """
        从进程内缓存获取 token，若未过期则返回。
        """
        global _WECOM_ACCESS_TOKEN, _WECOM_TOKEN_EXPIRES_AT
        now = time.time()
        if _WECOM_ACCESS_TOKEN and now < _WECOM_TOKEN_EXPIRES_AT:
            return _WECOM_ACCESS_TOKEN
        return None

    def get_token(self, params=None):
        """
        覆盖基类：企业微信使用应用级 access_token，与单个用户无关。
        """
        token = self._get_cached_token()
        if token:
            return token
        # 本平台忽略 params，由 corp_id + corp_secret 重新获取 token
        return self.refresh_token()

    def refresh_token(self, params=None):
        """
        通过企业微信的 gettoken 接口获取 / 刷新应用级 access_token。
        文档：https://developer.work.weixin.qq.com/document/path/91039
        """
        global _WECOM_ACCESS_TOKEN, _WECOM_TOKEN_EXPIRES_AT

        if not self.corp_id or not self.corp_secret:
            print("[WeCom] 缺少 corp_id 或 corp_secret，无法刷新 access_token")
            return None

        try:
            # 使用统一的 use_request 请求体系获取企业微信应用 access_token
            token_req = use_request(apis.wecom_auth.get_token, {"loading": False})
            data = token_req.fetch() or {}
            errcode = data.get("errcode")
            if errcode == 0:
                access_token = data.get("access_token")
                expires_in = data.get("expires_in", 7200)

                # 留出一定缓冲时间，避免边界时刻过期
                _WECOM_ACCESS_TOKEN = access_token
                _WECOM_TOKEN_EXPIRES_AT = time.time() + max(0, expires_in - 300)

                print("[WeCom] access_token 刷新成功")
                return access_token

            print(f"[WeCom] 刷新 access_token 失败: {data}")
        except Exception as e:
            print(f"[WeCom] 刷新 access_token 异常: {e}")

        return None

    def _is_token_expired(self, response):
        """
        根据企业微信错误码判断 token 是否过期/无效。
        常见错误码：
        - 40014: invalid access_token
        - 42001: access_token expired
        - 41001: access_token missing
        - 40001: invalid credential
        """
        try:
            data = response.json()
            errcode = data.get("errcode")
            if errcode in [40014, 42001, 41001, 40001]:
                return True
        except Exception:
            pass
        return False

    # ---------- 请求/响应拦截 ----------

    def set_request_interceptors(self, config):
        """
        覆盖基类：将 access_token 自动追加到 query params，而不是 Authorization 头。
        """
        # 企业微信主要通过 ?access_token=xxx 进行认证
        token = self.get_token(config.get("params") or config.get("json") or {})

        if token:
            params = config.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            params = params.copy()
            params.setdefault("access_token", token)
            config["params"] = params

        # 仍然添加通用请求头（User-Agent 等）
        headers = self.get_request_headers()
        if "headers" not in config:
            config["headers"] = {}
        config["headers"].update(headers)
        return config

    def get_request_headers(self):
        """
        企业微信大多数接口为 JSON 请求，这里统一加上 JSON Content-Type。
        """
        headers = super().get_request_headers()
        headers.update({"Content-Type": "application/json; charset=utf-8"})
        return headers


