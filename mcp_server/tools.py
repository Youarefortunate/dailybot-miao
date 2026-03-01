import json
from typing import Any, Dict
from fastmcp import FastMCP
from loguru import logger as log
from main import main as dailybot_main
from common import config


def register_tools(mcp: FastMCP):
    """
    注册 MCP 工具
    :param mcp: FastMCP 实例
    """

    @mcp.tool()
    async def run_daily_report() -> str:
        """
        手动触发 DailyBot 的完整流程。
        包含环境自检、授权检测、数据采集、AI 总结和推送流程。
        """
        log.info("🚀 [MCP] 工具触发: run_daily_report")
        try:
            # 运行项目主逻辑，包含完整生命周期
            await dailybot_main()
            return "✅ DailyBot 工作流执行完毕。"
        except Exception as e:
            log.error(f"❌ [MCP] 工具执行异常: {e}")
            return f"执行失败: {str(e)}"

    @mcp.tool()
    def get_enabled_workflows() -> str:
        """
        获取当前已启用的工作流列表。
        """
        try:
            enabled = config.get("ENABLED_WORKFLOWS", [])
            log.info(f"🔍 [MCP] 获取已启用的工作流: {enabled}")
            return json.dumps(list(enabled), ensure_ascii=False)
        except Exception as e:
            log.error(f"❌ [MCP] 工具执行异常: {e}")
            return json.dumps([], ensure_ascii=False)

    @mcp.tool()
    def get_system_config() -> Dict[str, Any]:
        """
        查看当前系统的关键配置信息（脱敏）。
        """
        try:
            platforms = config.get_crawler_source_platforms()
            config_summary = {
                "enabled_platforms": platforms,
                "workflows": list(config.get("ENABLED_WORKFLOWS", [])),
            }
            log.info("🔍 [MCP] 正在查询系统配置摘要")
            return config_summary
        except Exception as e:
            log.error(f"❌ [MCP] 工具执行异常: {e}")
            return {"error": str(e)}

    log.info("✨ [MCP] 工具注册成功")
