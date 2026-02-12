import sys
from loguru import logger
from common.config import config

# 移除 loguru 默认的 stderr handler
logger.remove()

# 添加控制台输出 handler，使用项目配置的日志级别
logger.add(
    sys.stdout,
    level=config.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

# 添加文件日志输出（按天轮转，保留 7 天）
logger.add(
    "logs/dailybot_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}",
    rotation="00:00",
    retention="7 days",
    encoding="utf-8",
)
