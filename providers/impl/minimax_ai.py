from api import apis
from request.hooks.use_request import use_request
from ..modules.ai_factory import AIFactory


class MinimaxAI(AIFactory):
    """
    Minimax (海螺 AI) 总结供应商实现
    """

    AI_PROVIDER_NAME = "minimax"

    def __init__(self):
        """
        初始化 Minimax 供应商并绑定接口
        """
        super().__init__(name="minimax")
        # 绑定已注册的 api 模块 (由 api/modules/ai/minimax.py 动态加载)
        self.api_reqs["chat_completions"] = use_request(apis.ai_minimax.chat_completions)
