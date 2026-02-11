import functools
import threading
from abc import ABC, abstractmethod
from loguru import logger
from .workflow_manager import workflow_manager


class BaseWorkflow(ABC):
    """
    工作流基类，定义报告生成的生命周期钩子
    """

    WORKFLOW_NAME = "unknown"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.WORKFLOW_NAME != "unknown":
            workflow_manager.register_workflow(cls.WORKFLOW_NAME, cls)

    @abstractmethod
    def prepare(self) -> bool:
        """
        准备阶段：检查授权、配置等。
        返回 True 表示就绪，False 表示跳过或出错。
        """
        pass

    @abstractmethod
    def on_report_start(self, raw_report: str) -> dict:
        """
        开始阶段：AI 总结前执行（如发送占位符）。
        :return: 上下文数据 (context)，将传递给后续钩子
        """
        return {}

    @abstractmethod
    def summarize(self, raw_report: str) -> str:
        """
        执行 AI 总结逻辑
        """
        pass

    @abstractmethod
    def on_report_success(self, summary: str, context: dict):
        """
        成功阶段：AI 总结成功后执行（如更新最终内容）。
        """
        pass

    def on_report_failure(self, error_msg: str, context: dict):
        """
        失败阶段：处理异常情况（默认行为可由子类覆盖）。
        """
        failure_msg = f"⚠️ AI 总结服务异常\n> 错误原因: {error_msg}"
        self.on_report_success(failure_msg, context)
