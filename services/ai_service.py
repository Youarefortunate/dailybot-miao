from loguru import logger
from api import apis
from request.hooks.use_request import use_request
from config import config
from prompts import prompts


def summarize_text(text, provider="doubao"):
    """
    通用 AI 总结函数
    :param text: 待总结的文本
    :param provider: 模型供应商 (如 "doubao")
    """
    if provider == "doubao":
        return _summarize_with_doubao(text)

    logger.warning(f"未知的 AI 供应商: {provider}，尝试使用豆包作为默认。")
    return _summarize_with_doubao(text)


def _summarize_with_doubao(text):
    """私有实现的豆包总结逻辑"""
    ai_req = use_request(apis.ai_doubao.chat_completions)

    db_prompts = prompts.get("doubao", {})
    system_prompt = getattr(db_prompts, "system", "你是一个日报总结助手。")
    user_template = getattr(db_prompts, "user", "")

    user_content = f"{user_template}\n{text}" if user_template else text

    try:
        res_data = ai_req.fetch(
            {
                "model": config.DOUBAO_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "timeout": 60,
            }
        )
        return (
            res_data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "总结失败")
        )
    except Exception as e:
        logger.error(f"❌ 豆包 AI 总结出错: {e}")
        return "总结失败"
