def get_contact_api():
    """
    飞书联系人模块 API 定义 (使用 tenant_access_token)
    """
    return {
        "platform": "feishu",
        # 获取用户信息 (用于获取姓名)
        "get_user_info": {
            "method": "GET",
            "auth_type": "app",
            "url": "/open-apis/contact/v3/users/{user_id}",
        },
    }
