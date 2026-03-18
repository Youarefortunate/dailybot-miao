import os
import sys
from loguru import logger
from common.config import config
from utils.path_helper import get_app_dir, cleanup_old_files

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

# 因为路径中带有 {time} 时，loguru 的内置 retention 会失效。
# 这里我们执行一次手动扫描，清理 7 天前的过旧日志文件
try:
    log_dir = os.path.dirname(log_path)
    # 假设文件名格式为 dailybot_YYYY-MM-DD.log
    # 我们根据后缀 .log 和 前缀 dailybot_ 尝试匹配并清理
    cleanup_count = cleanup_old_files(
        log_dir, ".log", 7, date_format="dailybot_%Y-%m-%d"
    )
    if cleanup_count > 0:
        logger.info(f"💾 [日志自动清理] 发现并清除了 {cleanup_count} 个过期日志文件。")
except Exception:
    pass
