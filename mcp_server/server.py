import os
import sys
import common.logger
from fastmcp import FastMCP
from loguru import logger as log
from mcp_server.tools import register_tools
from utils.path_helper import get_root_path

project_root = get_root_path()
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class MCPServer:
    """
    MCP 服务器核心类
    负责初始化 FastMCP 实例并注册所有可用工具
    """

    def __init__(self):
        # FastMCP 实例，定义服务名称
        self.mcp = FastMCP("DailyBot")
        self._setup()

    def _setup(self):
        """
        配置服务器并注册工具
        """
        log.info("🚀 [MCP] 正在初始化 DailyBot MCP 服务器...")
        register_tools(self.mcp)

    def run(self):
        """
        启动 MCP 服务器
        """
        self.mcp.run()


if __name__ == "__main__":
    server = MCPServer()
    server.run()
