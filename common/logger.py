import sys
from loguru import logger
from common.config import config

# 获取日志配置
log_cfg = config.get("log", {})
log_level = log_cfg.get("level", "INFO")
file_level = log_cfg.get("file_level", "DEBUG")
log_path = log_cfg.get("path", "logs/dailybot_{time:YYYY-MM-DD}.log")
log_rotation = log_cfg.get("rotation", "00:00")
log_retention = log_cfg.get("retention", "7 days")

# 移除 loguru 默认的 stderr handler
logger.remove()

# 添加控制台输出 handler
logger.add(
    sys.stdout,
    level=log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

# 添加文件日志输出
logger.add(
    log_path,
    level=file_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}",
    rotation=log_rotation,
    retention=log_retention,
    encoding="utf-8",
)
