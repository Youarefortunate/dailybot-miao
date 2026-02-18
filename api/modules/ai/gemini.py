def get_gemini_api():
    """
    Google Gemini API 定义
    """
    return {
        "platform": "gemini",
        "chat_completions": "POST /models/{model}:generateContent",
    }
