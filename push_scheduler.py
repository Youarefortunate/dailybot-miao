from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
import main
import json
import os
from common.config import config
from token_storage import get_platform_storage, load_all_tokens


def refresh_all_tokens():
    """动态刷新配置启用的平台及所有用户的 access_token"""
    tokens = load_all_tokens()

    enabled_workflows = getattr(config, "ENABLED_WORKFLOWS", [])

    for platform in enabled_workflows:
        platform_key = platform.lower()
        platform_tokens = tokens.get(platform_key, {})
        storage = get_platform_storage(platform_key)

        for identifier in platform_tokens.keys():
            storage.refresh_token(identifier)


def job():
    """
    定时执行的任务函数
    """
    logger.info("[定时任务] 开始自动推送日报/周报...")
    # 先刷新所有用户的token
    logger.info("[定时任务] 刷新所有用户token...")
    refresh_all_tokens()
    # 执行推送任务
    main.main()


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(job, "cron", hour=00, minute=31)
    logger.info("定时推送服务已启动，每天18:20自动推送")
    scheduler.start()
