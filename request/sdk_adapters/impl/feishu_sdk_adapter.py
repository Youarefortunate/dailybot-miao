import lark_oapi as lark
from loguru import logger
from common.config import Config
from ..modules.base_sdk_adapter import BaseSDKAdapter


class FeishuSDKAdapter(BaseSDKAdapter):
    """
    飞书官方 SDK 适配器
    """

    SDK_ADAPTER_NAME = "feishu"

    def __init__(self, config=None):
        super().__init__(config)
        self.app_id = self.config.get("app_id", Config.FEISHU_APP_ID)
        self.app_secret = self.config.get("app_secret", Config.FEISHU_APP_SECRET)
        self.init_sdk()

    def init_sdk(self):
        """
        初始化飞书 SDK
        """
        if not self.app_id or not self.app_secret:
            logger.warning(
                "[FeishuSDKAdapter] 未提供 app_id 或 app_secret，SDK 初始化跳过"
            )
            return

        self.client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
        )
