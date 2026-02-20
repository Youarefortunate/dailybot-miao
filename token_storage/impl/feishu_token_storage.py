from typing import Optional, Dict, Any
from loguru import logger
from request.hooks import use_request
from api import apis
from ..modules.base_token_storage import BaseTokenStorage


class FeishuTokenStorage(BaseTokenStorage):
    """
    飞书 Token 存储实现
    """

    STORAGE_PLATFORM_NAME = "feishu"
    KEY_ACCESS_TOKEN = "access_token"  # 飞书用户token
    KEY_APP_TOKEN = "app_token"  # 飞书自建应用token
    KEY_REFRESH_TOKEN = "refresh_token"  # 飞书用户token刷新

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        super().__init__(data)
        self._temp_app_token: Optional[str] = None

    def get_token(self, identifier: str = None, **kwargs) -> Optional[str]:
        if not identifier:
            identifier = self.get_current_open_id()

        info = self._data.get(identifier) if self._data else None
        if info and isinstance(info, dict):
            return info.get(self.KEY_ACCESS_TOKEN)
        return None

    def get_app_token(
        self, identifier: str = None, force_refresh: bool = False, **kwargs
    ) -> Optional[str]:
        if not force_refresh:
            if not identifier:
                identifier = self.get_current_open_id()

            if identifier:
                info = self._data.get(identifier) if self._data else None
                if info and isinstance(info, dict) and info.get(self.KEY_APP_TOKEN):
                    return info[self.KEY_APP_TOKEN]

            if self._temp_app_token:
                return self._temp_app_token

        return self._fetch_and_sync_app_token()

    def refresh_token(
        self,
        identifier: str = None,
        tenant_access_token: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        refresh_tk = self.get_refresh_token(identifier)
        if not refresh_tk:
            logger.warning(f"[Feishu] 刷新失败：未找到 {identifier} 的 refresh_token")
            return None

        try:
            if not tenant_access_token:
                tenant_access_token = self.get_app_token(identifier=identifier)

            if not tenant_access_token:
                return None

            refresh_req = use_request(apis.feishu_user_auth.refresh_user_token)
            data = refresh_req.fetch(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_tk,
                    "headers": {"Authorization": f"Bearer {tenant_access_token}"},
                }
            )

            if data and self.KEY_ACCESS_TOKEN in data:
                new_tk = data[self.KEY_ACCESS_TOKEN]
                new_ref_tk = data.get(self.KEY_REFRESH_TOKEN, refresh_tk)
                self.save_token(
                    identifier, new_tk, new_ref_tk, app_token=tenant_access_token
                )
                return new_tk

            logger.error(f"[Feishu] {identifier} Token 刷新失败: {data}")
        except Exception as e:
            logger.error(f"[Feishu] {identifier} Token 刷新异常: {e}")
        return None

    def save_token(
        self,
        identifier: str,
        access_token: str,
        refresh_token: str,
        app_token: Optional[str] = None,
        **kwargs,
    ):
        token_info = {
            self.KEY_ACCESS_TOKEN: access_token,
            self.KEY_REFRESH_TOKEN: refresh_token,
            self.KEY_APP_TOKEN: app_token,
        }
        self._data[identifier] = token_info
        if self.factory:
            self.factory.set_platform_entry(
                self.STORAGE_PLATFORM_NAME, identifier, token_info
            )
        logger.debug(f"[Feishu] 已保存 identifier={identifier} 的 Token 信息")

    def get_refresh_token(self, identifier: str) -> Optional[str]:
        info = self._data.get(identifier) if self._data else None
        if info and isinstance(info, dict):
            return info.get(self.KEY_REFRESH_TOKEN)
        return None

    def get_current_open_id(self) -> Optional[str]:
        if not self._data:
            return None
        return next(iter(self._data.keys()))

    def clear_temp_app_token(self):
        self._temp_app_token = None

    def _fetch_and_sync_app_token(self) -> Optional[str]:
        try:
            req = use_request(apis.feishu_app_auth.get_tenant_token)
            data = req.fetch()
            new_token = data.get("tenant_access_token") if data else None

            if new_token:
                self._temp_app_token = new_token
                updated = False
                for oid, info in self._data.items():
                    if isinstance(info, dict):
                        info[self.KEY_APP_TOKEN] = new_token
                        if self.factory:
                            self.factory.set_platform_entry(
                                self.STORAGE_PLATFORM_NAME, oid, info
                            )
                        updated = True

                return new_token
        except Exception as e:
            logger.error(f"[Feishu] 在线获取 app_token 异常: {e}")
        return None
