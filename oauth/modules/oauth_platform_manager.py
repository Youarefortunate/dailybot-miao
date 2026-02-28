import os
from fastapi import FastAPI
from loguru import logger
from utils.dynamic_manager import BaseDynamicManager
from common.config import config
from exceptions import GlobalExceptionHandler


class OATHPlatformManager(BaseDynamicManager):
    """
    OATH 平台管理器
    负责动态发现和注册 OATH 平台实现，并接管 FastAPI 实例和路由挂载。
    """

    def __init__(self):
        # 确定 oauth/impl 目录的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # current_dir 是 oauth/modules/，上一级是 oauth/，再下一级是 impl/
        impl_dir = os.path.join(os.path.dirname(current_dir), "impl")

        # 初始化基类
        super().__init__(
            impl_dir_path=impl_dir,
            module_prefix="oauth.impl",
            name_templates=["{key}_oauth_platform", "{key}_platform", "{key}"],
        )
        self._instances = {}
        self._app = None
        self._initialized = False

    @property
    def app(self) -> FastAPI:
        """
        获取 FastAPI 应用实例（延迟初始化）
        """
        if self._app is None:
            self._app = FastAPI()
            # 注册全局异常处理器
            GlobalExceptionHandler.register(self._app)
            # 首次访问 app 时，确保所有平台已发现并挂载路由
            self._ensure_initialized()
        return self._app

    def _ensure_initialized(self):
        """
        确保管理器已完成初始化（全量发现和路由挂载）
        """
        if not self._initialized:
            # 此时 oauth_platform_manager 变量已在模块中定义并赋值
            # 执行全量模块发现
            self.ensure_fully_discovered()
            # 注册路由（如果 app 已经存在）
            if self._app:
                self._register_routes_to_app()
            self._initialized = True

    def register_oath_platform(self, name, platform_class):
        """
        注册 OATH 平台类
        """
        self.register(name, platform_class)

    def get_oath_platform_class(self, name):
        """
        获取 OATH 平台类
        """
        return self.get_class(name)

    def get_registered_oath_platforms(self):
        """
        获取所有已注册的 OATH 平台名称
        """
        return self.get_all_keys()

    def _register_routes_to_app(self):
        """
        将所有已注册平台的路由挂载到 FastAPI 实例
        """
        for platform_name in self.get_registered_oath_platforms():
            inst = self._get_instance(platform_name)
            if inst and hasattr(inst, "router"):
                logger.info(f"[OATH] 注册路由: /{platform_name}")
                self._app.include_router(
                    inst.router, prefix=f"/{platform_name}", tags=[platform_name]
                )

    def _get_instance(self, platform_name):
        """
        获取（或创建）平台的单例实例
        """
        if platform_name in self._instances:
            return self._instances[platform_name]

        platform_class = self.get_oath_platform_class(platform_name)
        if platform_class:
            inst = platform_class()
            self._instances[platform_name] = inst
            return inst
        return None

    async def send_auth_nudge(self):
        """
        通用授权引导调度器。
        """
        # 确保已初始化（发现各平台实现）
        self._ensure_initialized()

        enabled_platforms = getattr(config, "ENABLED_WORKFLOWS")
        results = []

        for platform_name in enabled_platforms:
            inst = self._get_instance(platform_name)
            if inst:
                logger.info(f"[OATH] 正在尝试调度平台引导: {platform_name}")
                success, reason = await inst.send_auth_nudge()
                results.append((success, reason))
            else:
                logger.warning(f"[OATH] 未找到平台实现: {platform_name}")
                results.append((False, f"Platform {platform_name} not found"))

        # 只要有一个成功就返回成功
        success = any(r[0] for r in results)
        error_reasons = [r[1] for r in results if not r[0] and r[1]]

        return success, "; ".join(error_reasons) if error_reasons else None

    def get_oath_server_config(self) -> dict:
        """
        获取当前活动（启用的且在 OATH 管理器中注册的）平台的 Web 服务器配置。
        返回包含 host, port, log_level 等参数的字典
        """
        enabled_platforms = getattr(config, "ENABLED_WORKFLOWS", [])
        oath_required = self.get_registered_oath_platforms()

        for p_name in enabled_platforms:
            if p_name in oath_required:
                inst = self._get_instance(p_name)
                if inst:
                    return inst.oauth_config

        # 降级默认值
        return {"host": "0.0.0.0", "port": 8001, "log_level": "error"}


oauth_platform_manager = OATHPlatformManager()
