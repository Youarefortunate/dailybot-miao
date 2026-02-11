from loguru import logger
from api import apis
from request.hooks.use_request import use_request
from config import config
from prompts import prompts
from ..modules.base_ai import BaseAIProvider


class DoubaoAI(BaseAIProvider):
    """
    豆包 AI 总结供应商实现
    """

    AI_PROVIDER_NAME = "doubao"

    def __init__(self):
        self.ai_req = use_request(apis.ai_doubao.chat_completions)

    def summarize(self, text: str) -> str:
        """
        使用豆包专属 Prompt 和参数进行总结
        """
        # 获取专属提示词配置
        db_prompts = prompts.get("doubao", {})
        system_prompt = getattr(db_prompts, "system", "你是一个日报总结助手。")
        user_template = getattr(db_prompts, "user", "")

        # 拼接 Prompt
        user_content = f"{user_template}\n{text}" if user_template else text

        try:
            res_data = self.ai_req.fetch(
                {
                    "model": config.DOUBAO_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "timeout": 60,
                }
            )
            content = (
                res_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

            if not content:
                logger.warning(f"[{self.AI_PROVIDER_NAME}] 总结返回内容为空")
                return "总结失败"

            return content

        except Exception as e:
            logger.error(f"[{self.AI_PROVIDER_NAME}] 总结过程出错: {e}")
            return f"总结失败: {e}"
