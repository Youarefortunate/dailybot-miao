def get_openai_api():
    """
    OpenAI API 定义
    """
    return {
        "platform": "openai",
        "chat_completions": "POST /chat/completions",
    }
