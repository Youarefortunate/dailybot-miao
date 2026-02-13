from loguru import logger
from api import apis
from request.hooks.use_request import use_request
from common.config import config
from prompts import prompts
from ..modules.base_ai import BaseAIProvider


class GlmAI(BaseAIProvider):
    """
    智谱 GLM AI 总结供应商实现
    """

    AI_PROVIDER_NAME = "glm"

    def __init__(self):
        self.ai_req = use_request(apis.ai_glm.chat_completions)

    def summarize(self, text: str) -> str:
        """
        使用 GLM 专属 Prompt 和参数进行总结
        """
        # 获取专属提示词配置
        glm_prompts = prompts.get("glm", {})
        system_prompt = getattr(glm_prompts, "system", "你是一个日报总结助手。")
        user_template = getattr(glm_prompts, "user", "")

        # 拼接 Prompt
        user_content = f"{user_template}\n{text}" if user_template else text

        # 获取模型配置和自定义参数
        model_cfg = config.get_model(self.AI_PROVIDER_NAME)
        model_id = config.GLM_MODEL
        custom_params = model_cfg.get("params", {})

        # 构建请求参数
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        # 合并自定义参数 (如 timeout, temperature 等)
        if custom_params:
            payload.update(custom_params)

        try:
            res_data = self.ai_req.fetch(payload)

            # API 响应通常已经由 use_request 解包
            if isinstance(res_data, dict) or hasattr(res_data, "get"):
                content = (
                    res_data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
            else:
                content = str(res_data)

            if not content:
                logger.warning(f"[{self.AI_PROVIDER_NAME}] 总结返回内容为空")
                return "[]"

            # 清理 Markdown 代码块标记，确保返回纯 JSON
            content = content.replace("```json", "").replace("```", "").strip()
            return content

        except Exception as e:
            logger.error(f"[{self.AI_PROVIDER_NAME}] 总结过程出错: {e}")
            return "[]"
