def get_doubao_api():
    """
    豆包大模型 API 定义
    """
    return {
        "platform": "doubao",
        # 聊天补全接口
        "chat_completions": "POST /chat/completions",
    }
