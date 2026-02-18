from loguru import logger
from api import apis
from request.hooks.use_request import use_request
from ..modules.ai_factory import AIFactory
from common.config import config


class GeminiAI(AIFactory):
    """
    Gemini 总结服务实现
    """

    AI_PROVIDER_NAME = "gemini"

    def __init__(self):
        super().__init__(name="gemini")
        # 绑定已注册的 api 模块
        self.api_reqs["chat_completions"] = use_request(apis.ai_gemini.chat_completions)

    def summarize(self, text: str) -> str:
        """
        Gemini 专用的请求封装，仅负责构造符合规范的 Payload
        """
        if not self.model_cfg:
            self.model_cfg = config.get_model(self.AI_PROVIDER_NAME)

        cfg = self.model_cfg
        model_id = cfg.get("model")

        # 确保 payload 符合 Gemini 规范
        if not cfg.get("payload"):
            cfg["payload"] = {"contents": [{"parts": [{"text": "{system}\n\n{user}"}]}]}

        # 注入 model 以便 ApiRegister 替换 URL 中的 {model} 占位符
        if model_id:
            if "params" not in cfg:
                cfg["params"] = {}
            cfg["params"]["model"] = model_id

        return super().summarize(text)

    def _parse_response(self, res_data: any) -> str:
        """
        重写响应解析，适配 Gemini 的 candidates[0].content.parts[0].text 结构
        """
        try:
            if isinstance(res_data, dict):
                candidates = res_data.get("candidates", [])
                if candidates:
                    content_obj = candidates[0].get("content", {})
                    parts = content_obj.get("parts", [])
                    if parts:
                        text = parts[0].get("text", "")
                        if text:
                            return (
                                text.replace("```json", "").replace("```", "").strip()
                            )
        except Exception:
            pass

        # 降级到基类的通用解析
        return super()._parse_response(res_data)
