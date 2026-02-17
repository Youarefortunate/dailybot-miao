from api import apis
from request.hooks.use_request import use_request
from ..modules.ai_factory import AIFactory


class GlmAI(AIFactory):
    """
    智谱 GLM AI 总结供应商实现
    """

    AI_PROVIDER_NAME = "glm"

    def __init__(self):
        # 指定名称，基类会自动关联 config.yaml 中的模型配置和提示词
        super().__init__(name="glm")
        # 绑定已注册的 api 模块
        self.api_reqs["chat_completions"] = use_request(apis.ai_glm.chat_completions)
