from api import apis
from request.hooks.use_request import use_request
from ..modules.ai_factory import AIFactory


class DoubaoAI(AIFactory):
    """
    豆包 AI 总结供应商实现
    """

    AI_PROVIDER_NAME = "doubao"

    def __init__(self):
        super().__init__(name="doubao")
        # 绑定已注册的 api 模块
        self.api_reqs["chat_completions"] = use_request(apis.ai_doubao.chat_completions)
