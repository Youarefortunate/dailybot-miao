from api import apis
from request.hooks.use_request import use_request
from ..modules.ai_factory import AIFactory


class OpenAIAI(AIFactory):
    """
    OpenAI 总结服务实现，遵循标准 AIFactory 流程
    """

    AI_PROVIDER_NAME = "openai"

    def __init__(self):
        """
        初始化 OpenAI 供应商并绑定接口
        """
        super().__init__(name="openai")
        self.api_reqs["chat_completions"] = use_request(apis.ai_openai.chat_completions)

    def get_default_payload_template(self, model_id: str) -> dict:
        """
        如果是 reasoning 模型（o1/o3/o4 系列），定制 developer 角色的 payload 结构模板。
        否则使用默认的标准结构模板。
        """
        if self._is_reasoning_model(model_id):
            return {
                "model": "{model}",
                "messages": [
                    {
                        "role": "developer",
                        "content": "Formatting re-enabled\n{system}",
                    },
                    {"role": "user", "content": "{user}"},
                ],
            }
        return super().get_default_payload_template(model_id)

    def _is_reasoning_model(self, model_id: str) -> bool:
        """
        判断是否为 reasoning 模型（内部判断）
        """
        prefixes = ("o1", "o3", "o4")
        return model_id is not None and any(model_id.startswith(p) for p in prefixes)
