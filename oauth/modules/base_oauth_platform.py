from fastapi import APIRouter
from loguru import logger
from common.config import config
from .oauth_platform_manager import oauth_platform_manager


class BaseOATHPlatform:
    """
    OATH 平台基类
    所有具体的 OATH 平台实现都应继承此类
    """

    OATH_PLATFORM_NAME = "unknown"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 自动注册到管理器
        if cls.OATH_PLATFORM_NAME != "unknown":
            oauth_platform_manager.register_oath_platform(cls.OATH_PLATFORM_NAME, cls)

    def __init__(self, config_dict=None):
        self.config = config_dict or {}
        self.router = APIRouter()
        self.register_routes(self.router)

    @property
    def oauth_config(self) -> dict:
        """
        获取当前平台 OAuth 回调服务器的规整化配置
        包含 host, port, log_level 等 uvicorn 配置参数
        """
        # 默认配置
        default_cfg = {"host": "0.0.0.0", "port": 8001, "log_level": "error"}

        # 从全局配置中获取该平台的私有配置
        platform_cfg = config.get(f"platforms.{self.OATH_PLATFORM_NAME}.oauth", {})
        if not isinstance(platform_cfg, dict):
            platform_cfg = {}

        # 合并配置，平台私有配置优先
        return {**default_cfg, **platform_cfg}

    def register_routes(self, router: APIRouter):
        """
        注册平台相关的路由
        默认为 /callback 路由，子类可覆盖或扩展
        """
        router.add_api_route("/callback", self.callback, methods=["GET"])

    async def callback(self, code: str, state: str = None):
        """
        处理授权回调的默认入口
        """
        raise NotImplementedError("Subclasses must implement the callback method")

    def get_oath_platform_name(self):
        return self.OATH_PLATFORM_NAME

    async def send_auth_nudge(self):
        """
        主动推送授权引导（Nudge）。
        子类需实现具体的推送逻辑。
        返回 (success, error_reason)
        """
        return False, f"[{self.OATH_PLATFORM_NAME}] send_auth_nudge not implemented"
