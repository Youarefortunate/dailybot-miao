import asyncio
import os
import random
from collections import defaultdict
from loguru import logger
from common.config import config
from prompts import prompts
from utils.dynamic_manager import BaseDynamicManager
from .camouflage_history import camouflage_history_manager


class CrawlerManager(BaseDynamicManager):
    """
    爬虫管理器
    继承通用工具类，支持动态发现和自动注册爬虫子类
    """

    def __init__(self):
        # 确定 impl 目录相对于项目根目录的路径
        impl_dir = os.path.join("crawlers", "impl")

        # 初始化基类
        super().__init__(
            impl_dir_path=impl_dir,
            module_prefix="crawlers.impl",
            name_templates=["{key}_crawler", "{key}"],
        )

    def register_crawler(self, crawler_name: str, crawler_class):
        """
        注册爬虫类
        """
        self.register(crawler_name, crawler_class)

    def get_crawler_class(self, name: str):
        """
        获取爬虫类
        """
        return self.get_class(name)

    def get_registered_platforms(self) -> list:
        """
        获取所有已注册的平台名称
        """
        return self.get_all_keys()

    async def collect_and_camouflage(self) -> tuple[str, int, bool, list]:
        """
        采集所有活跃平台的数据。
        如需伪装，在此处一并进行填补和合并，最后向外部仅返回结构化的结论内容与提示词。
        返回: (最终上报文本, 最终上报提交总数量, 是否触发伪装, 此次使用的伪装记录项对象列表)
        """
        logger.info("📋 正在采集所有平台的活动记录...")
        report_text = ""
        total_real_count = 0
        fake_items_used = []
        extra_prompts = None
        has_camouflage_triggered = False

        configured_platforms = config.get_crawler_source_platforms()

        # 1. 第一步：并行抓取所有平台的真实活跃数据与额外补充记录
        crawl_tasks = []
        extra_tasks = []
        active_crawler_instances = []
        platform_names = []

        for p_name in configured_platforms:
            # 检查采集源是否启用，默认为开启
            is_enabled = config.get(f"crawler_sources.{p_name}.enabled", True)
            if not (is_enabled is True or str(is_enabled).lower() == "true"):
                logger.info(f"🚫 [系统] 采集源 {p_name} 已显式禁用，跳过。")
                continue

            crawler_cls = self.get_crawler_class(p_name)
            if not crawler_cls:
                logger.warning(f"⚠️ 平台 {p_name} 未找到爬虫实现，跳过。")
                continue

            crawler_instance = crawler_cls()
            platform_upper = p_name.upper()
            target_user = getattr(config, f"{platform_upper}_TARGET_USER", None)

            # 抓取真实活动
            crawl_tasks.append(crawler_instance.crawl(target_user=target_user))
            # 抓取额外报告（如果支持）
            if hasattr(crawler_instance, "fetch_extra_report"):
                extra_tasks.append(crawler_instance.fetch_extra_report())
            else:
                extra_tasks.append(asyncio.sleep(0, result={}))  # 占位

            active_crawler_instances.append(crawler_instance)
            platform_names.append(p_name)

        if not crawl_tasks:
            return "", 0, False, []

        # 并行抓取
        all_results = await asyncio.gather(*crawl_tasks, *extra_tasks)
        real_results = all_results[: len(crawl_tasks)]
        extra_results = all_results[len(crawl_tasks) :]

        # 2. 第二步：处理每个平台的结果，汇总生成嵌套报告
        platform_reports = []

        for i, (p_name, crawler_instance) in enumerate(
            zip(platform_names, active_crawler_instances)
        ):
            activities_map = real_results[i]
            extra_result = extra_results[i]

            # 获取本平台的显示名称
            p_display_name = crawler_instance.get_platform_name().upper()
            platform_header = f"\n  平台: {p_display_name}\n"
            platform_content = ""

            # 2.1 真实记录部分
            real_text, real_count = crawler_instance.generate_report(
                activities_map, indent=4
            )
            if real_text.strip():
                platform_content += f"    📦 [今日真实工作]\n{real_text}"

            # 2.2 计算是否触发伪装
            extra_report_part, extra_count = "", 0
            if extra_result:
                extra_report_part, extra_count = crawler_instance.generate_extra_report(
                    extra_result, indent=4
                )

            platform_contribution_count = real_count + extra_count
            total_real_count += platform_contribution_count

            # 获取伪装配置并判断
            source_cfg = config.get(f"crawler_sources.{p_name}", {})
            camou_cfg = source_cfg.get("camouflage", {})

            if camou_cfg.get(
                "enabled", False
            ) and platform_contribution_count <= camou_cfg.get("threshold", 0):
                max_items = camou_cfg.get("max_items", 0)
                needed = max_items - platform_contribution_count

                if needed > 0:
                    logger.info(
                        f"🎭 [伪装] 平台 {p_name} 实时贡献({platform_contribution_count}) <= 阈值，准备补全..."
                    )
                    try:
                        fake_items = await crawler_instance.generate_camouflage_data(
                            needed,
                            target_user=getattr(
                                config, f"{p_name.upper()}_TARGET_USER", None
                            ),
                            lookback_days=camou_cfg.get("lookback_days", 14),
                            cooldown_days=camou_cfg.get("cooldown_days", 10),
                        )

                        if fake_items:
                            fake_report_part = (
                                f"    🎭 [待伪装素材 - {p_display_name}]\n"
                            )
                            source_date_grouped = defaultdict(lambda: defaultdict(list))
                            for item in fake_items:
                                full_source = f"{item.source} ({item.repo_path})"
                                item_date = item.date or "未知日期"
                                source_date_grouped[full_source][item_date].append(item)
                                fake_items_used.append(item)

                            sorted_sources = sorted(source_date_grouped.keys())
                            for source_label in sorted_sources:
                                fake_report_part += f"      数据源: {source_label}\n"
                                date_map = source_date_grouped[source_label]
                                for date_str in sorted(date_map.keys(), reverse=True):
                                    fake_report_part += f"        📅 日期: {date_str}\n"
                                    for item in date_map[date_str]:
                                        fake_report_part += (
                                            f"          - {item.content}\n"
                                        )

                            platform_content += fake_report_part
                            has_camouflage_triggered = True
                    except Exception as e:
                        logger.error(f"❌ [伪装] 平台 {p_name} 提取失败: {e}")

            # 2.3 额外补充部分
            if extra_report_part.strip():
                platform_content += f"    📝 [额外信息补充]\n{extra_report_part}"
                if hasattr(crawler_instance, "archive_extra_report"):
                    crawler_instance.archive_extra_report()

            # 组装本平台完整报告
            if platform_content:
                platform_reports.append(platform_header + platform_content)

        # 合并所有平台
        return (
            "".join(platform_reports),
            total_real_count,
            has_camouflage_triggered,
            fake_items_used,
        )


# 单例
crawler_manager = CrawlerManager()
