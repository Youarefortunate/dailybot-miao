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

    def get_default_payload_template(self, model_id: str) -> dict:
        """
        定制 Gemini 特有的 payload 结构模板，带占位符。
        """
        return {"contents": [{"parts": [{"text": "{system}\n\n{user}"}]}]}

    async def summarize(self, text: str, is_camouflage: bool = False) -> str:
        """
        Gemini 专用的请求封装，主要用于注入特定的参数（如 model 放入 param）
        然后通过委托给父类进行 payload 模板组装。
        """
        if not self.model_cfg:
            self.model_cfg = config.get_model(self.AI_PROVIDER_NAME)

        cfg = self.model_cfg
        model_id = getattr(self, "model_id", None)
        if not model_id:
            model_id = cfg.get("model")
            if (
                not model_id
                and cfg.get("models")
                and isinstance(cfg.get("models"), list)
            ):
                model_id = cfg.get("models")[0]

        # 注入 model 以便 ApiRegister 替换 URL 中的 {model} 占位符
        if model_id:
            if "params" not in cfg:
                cfg["params"] = {}
            cfg["params"]["model"] = model_id

        return await super().summarize(text, is_camouflage=is_camouflage)

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
