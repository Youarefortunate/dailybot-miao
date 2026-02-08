def get_feishu_im_api():
    """
    飞书即时消息模块 API 定义
    """
    return {
        "platform": "feishu",
        # 发送消息 (支持卡片)
        "send_message": {
            "method": "POST",
            "url": "/open-apis/im/v1/messages",
            "params": {"receive_id_type": "chat_id"},
        },
    }
