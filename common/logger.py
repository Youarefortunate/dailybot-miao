import os
import sys
from loguru import logger
from common.config import config
from utils.path_helper import get_app_dir

# 获取日志配置
log_cfg = config.get("log", {})
log_level = log_cfg.get("level", "INFO")
file_level = log_cfg.get("file_level", "DEBUG")
log_path_raw = log_cfg.get("path", "logs/dailybot_{time:YYYY-MM-DD}.log")

# 强制将相对路径转换为基于程序运行目录的绝对路径
if not os.path.isabs(log_path_raw):
    log_path = os.path.join(get_app_dir(), log_path_raw)
else:
    log_path = log_path_raw

log_rotation = log_cfg.get("rotation", "00:00")
log_retention = log_cfg.get("retention", "7 days")

# 移除 loguru 默认的 stderr handler
logger.remove()

# 添加控制台输出 handler (仅当 stdout 有效时)
if sys.stdout is not None:
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
