def get_feishu_contact_api():
    """
    飞书联系人模块 API 定义
    """
    return {
        "platform": "feishu",
        # 获取用户信息 (用于获取姓名)
        "get_user_info": "GET /open-apis/contact/v3/users/{user_id}",
    }
