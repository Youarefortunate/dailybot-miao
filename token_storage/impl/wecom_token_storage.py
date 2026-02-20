import time
from typing import Optional
from loguru import logger
from ..modules.base_token_storage import BaseTokenStorage


class WeComTokenStorage(BaseTokenStorage):
    """
    企业微信 Token 存储实现 (带生命周期计算)
    """

    STORAGE_PLATFORM_NAME = "wecom"

    def get_token(self, identifier: str = "corp_app", **kwargs) -> Optional[str]:
        info = self._data.get(identifier) if self._data else None
        if info and isinstance(info, dict):
            expires_at = info.get("expires_at", 0)
            if time.time() < expires_at:
                return info.get("access_token")
            else:
                logger.debug(f"[WeCom] Token for {identifier} has expired.")
        return None

    def save_token(
        self, identifier: str, access_token: str, expires_in: int = 7200, **kwargs
    ):
        # 留出 300 秒缓冲时间，避免边界时刻过期
        expires_at = time.time() + max(0, expires_in - 300)
        token_info = {"access_token": access_token, "expires_at": expires_at}
        self._data[identifier] = token_info
        if self.factory:
            self.factory.set_platform_entry(
                self.STORAGE_PLATFORM_NAME, identifier, token_info
            )
        logger.debug(
            f"[WeCom] 已保存 identifier={identifier} 的 Token 信息，将在 {expires_at} 过期"
        )
