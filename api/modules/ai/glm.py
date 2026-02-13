def get_glm_api():
    """
    智谱 GLM 大模型 API 定义 (基于火山引擎部署)
    """
    return {
        "platform": "glm",
        # 聊天补全接口
        "chat_completions": "POST /chat/completions",
    }
