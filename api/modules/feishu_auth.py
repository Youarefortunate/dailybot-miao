from config import config

def get_feishu_auth_api():
    """
    飞书鉴权模块 API 定义
    """
    return {
        "platform": "feishu",
        
        # 获取自建应用的 tenant_access_token (机器人令牌)
        "get_tenant_token": {
            "method": "POST",
            "url": "/open-apis/auth/v3/tenant_access_token/internal/",
            "json": {
                "app_id": config.FEISHU_APP_ID,
                "app_secret": config.FEISHU_APP_SECRET
            }
        },
        
        # 使用 refresh_token 刷新用户 access_token
        "refresh_user_token": "POST /open-apis/authen/v1/refresh_access_token"
    }
