from loguru import logger
from workflows.modules.base_workflow import BaseWorkflow


class WeComWorkflow(BaseWorkflow):
    """
    企业微信工作流（占位）
    """

    WORKFLOW_NAME = "wecom"

    def prepare(self) -> bool:
        # TODO: 实现企微 Webhook 或自建应用授权检查
        # logger.info(f"[{self.WORKFLOW_NAME}] 正在检查企微就绪状态...")
        return True

    def on_report_start(self, raw_report: str) -> dict:
        # 企业微信通常使用 Webhook 直接推送，可能不需要占位符
        return {}

    def on_report_success(self, summary: str, context: dict):
        # TODO: 调用企微 API 推送最终内容
        # logger.info(f"[{self.WORKFLOW_NAME}] (模拟) 推送日报成功")
        pass

    def on_report_failure(self, error_msg: str, context: dict):
        # logger.error(f"[{self.WORKFLOW_NAME}] (模拟) 推送失败报告")
        pass
