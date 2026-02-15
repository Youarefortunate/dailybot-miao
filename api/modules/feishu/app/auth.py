from common.config import config


def get_auth_api():
    """
    飞书应用鉴权相关 API (使用 tenant_access_token)
    """
    return {
        "platform": "feishu",
        # 获取自建应用的 tenant_access_token (机器人令牌)
        "get_tenant_token": {
            "method": "POST",
            "url": "/open-apis/auth/v3/tenant_access_token/internal",
            "json": {
                "app_id": config.FEISHU_APP_ID,
                "app_secret": config.FEISHU_APP_SECRET,
            },
        },
    }
