from fastapi import APIRouter
from loguru import logger
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

    def __init__(self, config=None):
        self.config = config or {}
        self.router = APIRouter()
        self.register_routes(self.router)

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
