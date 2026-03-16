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
