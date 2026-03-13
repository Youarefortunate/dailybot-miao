from loguru import logger
from workflows.modules.base_workflow import BaseWorkflow
from providers import AIFactory
from common.config import config


class WeComWorkflow(BaseWorkflow):
    """
    企业微信工作流（占位）
    """

    WORKFLOW_NAME = "wecom"

    async def prepare(self) -> bool:
        # TODO: 实现企微 Webhook 或自建应用授权检查
        # logger.info(f"[{self.WORKFLOW_NAME}] 正在检查企微就绪状态...")
        return True

    async def on_report_start(self, raw_report: str) -> dict:
        # 企业微信通常使用 Webhook 直接推送，可能不需要占位符
        return {}

    async def summarize(self, raw_report: str, is_camouflage: bool = False) -> str:
        """
        执行 AI 总结逻辑
        """
        platform_config = config.get_platform(self.WORKFLOW_NAME)
        provider_key = platform_config.get("ai_model")

        if not provider_key:
            logger.error(f"[{self.WORKFLOW_NAME}] 未配置 AI 模型 (ai_model)。")
            raise ValueError("总结失败: 未配置 AI 模型")

        # 获取模型提供商名 (支持 provider 或 具体的大模型名 反查)
        provider_name = config.get_provider_for_model(provider_key) or provider_key

        ai_instance = AIFactory.get_ai(provider_name, model_id=provider_key)
        if not ai_instance:
            logger.error(
                f"[{self.WORKFLOW_NAME}] 未找到相关 AI 模型实现: {provider_name}"
            )
            raise ValueError(f"总结失败: 未找到相关 AI 模型实现 {provider_name}")

        return await ai_instance.summarize(raw_report, is_camouflage=is_camouflage)

    async def on_report_success(self, summary: str, context: dict):
        # TODO: 调用企微 API 推送最终内容
        # logger.info(f"[{self.WORKFLOW_NAME}] (模拟) 推送日报成功")
        # logger.error(f"[{self.WORKFLOW_NAME}] (模拟) 推送失败报告")
        pass
