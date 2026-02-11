def get_im_api():
    """
    飞书即时消息模块 API 定义 (使用 tenant_access_token)
    """
    return {
        "platform": "feishu",
        # 发送消息 (支持卡片)
        "send_message": {
            "method": "POST",
            "auth_type": "app",
            "url": "/open-apis/im/v1/messages",
            "params": {"receive_id_type": "chat_id"},
        },
        # 更新消息内容
        "update_message": {
            "method": "PATCH",
            "auth_type": "app",
            "url": "/open-apis/im/v1/messages/:message_id",
        },
    }
