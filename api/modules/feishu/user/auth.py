from common.config import config


def get_auth_api():
    """
    飞书用户鉴权相关 API (使用 user_access_token)
    """
    return {
        "platform": "feishu",
        # 使用 code 换取 user_access_token
        "get_access_token": {
            "method": "POST",
            "url": "/open-apis/authen/v1/access_token",
            "json": {
                "grant_type": "authorization_code",
                "app_id": config.FEISHU_APP_ID,
                "app_secret": config.FEISHU_APP_SECRET,
            },
        },
        # 使用 refresh_token 刷新用户 access_token
        "refresh_user_token": "POST /open-apis/authen/v1/refresh_access_token",
    }
