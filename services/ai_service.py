from loguru import logger
from api import apis
from request.hooks.use_request import use_request
from config import config
from prompts import prompts


def summarize_with_doubao(text):
    """使用豆包 AI 总结文本内容"""
    ai_req = use_request(apis.ai_doubao.chat_completions)

    # 获取提示词配置：优先从 prompts 加载，若缺失则提供兜底
    # 外部调用时能直接 prompts.doubao.system 访问
    db_prompts = prompts.get("doubao", {})
    system_prompt = getattr(db_prompts, "system", "你是一个日报总结助手。")
    user_template = getattr(db_prompts, "user", "")

    # 处理用户消息内容：拼接模板与日报文本
    user_content = f"{user_template}\n{text}" if user_template else text

    try:
        res_data = ai_req.fetch(
            {
                "model": config.DOUBAO_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
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
        logger.error(f"❌ AI 总结出错: {e}")
        return "总结失败"
