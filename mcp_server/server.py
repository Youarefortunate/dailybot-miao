import logging
import os
import subprocess
import sys
from pathlib import Path

# 获取项目根目录
_PROJECT_ROOT = str(Path(__file__).parent.parent.absolute())
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 强制设置工作目录为项目根，确保配置文件能被正确加载
# (Cursor 等 MCP 客户端的 cwd 设置可能不会生效)
os.chdir(_PROJECT_ROOT)

# 预检日志器 (在 loguru 可用之前使用 stdlib logging)
_preflight_logger = logging.getLogger("mcp.preflight")
_preflight_logger.addHandler(logging.StreamHandler(sys.stderr))
_preflight_logger.setLevel(logging.INFO)


def _preflight_check():
    """
    启动前环境自检：虚拟环境检测 + 关键依赖自动安装。
    在第三方库导入之前执行，确保运行环境就绪。
    """
    # 1. 虚拟环境检测
    in_venv = hasattr(sys, "prefix") and sys.prefix != sys.base_prefix
    if not in_venv:
        _preflight_logger.warning(
            "⚠️ [Preflight] 当前未在虚拟环境中运行，建议使用 .venv 的 Python 路径"
        )

    # 2. 关键依赖检测与自动安装
    try:
        __import__("fastmcp")
    except ImportError:
        _preflight_logger.info("📦 [Preflight] 检测到缺少关键依赖，正在自动安装...")
        req_file = os.path.join(_PROJECT_ROOT, "requirements.txt")
        if not os.path.exists(req_file):
            _preflight_logger.error(
                f"❌ [Preflight] 未找到 {req_file}，无法自动安装依赖"
            )
            sys.exit(1)
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", req_file],
                stdout=sys.stderr,
                stderr=subprocess.STDOUT,
            )
            _preflight_logger.info("✅ [Preflight] 依赖安装完成")
        except subprocess.CalledProcessError as e:
            _preflight_logger.error(f"❌ [Preflight] 依赖安装失败: {e}")
            sys.exit(1)


_preflight_check()

# ---- 预检通过，以下可安全导入第三方库 ----
from fastmcp import FastMCP
from loguru import logger as log
from mcp_server.tools import register_tools


class MCPServer:
    """
    MCP 服务器核心类
    负责初始化 FastMCP 实例并注册所有可用工具
    """

    def __init__(self):
        self._setup_logger()
        self.mcp = FastMCP("DailyBot")
        self._setup()

    def _setup_logger(self):
        """
        配置 MCP 模式下的日志输出。
        在 stdio 传输模式下，stdout 必须仅用于 JSON-RPC 通信，
        因此将所有日志重定向到 stderr，避免污染 stdout。
        """
        log.remove()
        log.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        )

    def _setup(self):
        """配置服务器并注册工具"""
        log.info("🚀 [MCP] 正在初始化 DailyBot MCP 服务器...")
        register_tools(self.mcp)

    def run(self):
        """启动 MCP 服务器（禁用 banner 以避免污染 stdio 通道）"""
        self.mcp.run(show_banner=False)


if __name__ == "__main__":
    server = MCPServer()
    server.run()
