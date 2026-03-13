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

        # 1. 第一步：并行抓取所有平台的真实活跃数据
        crawl_tasks = []
        active_crawler_instances = []
        platform_names = []

        for p_name in configured_platforms:
            crawler_cls = self.get_crawler_class(p_name)
            if not crawler_cls:
                logger.warning(f"⚠️ 平台 {p_name} 未找到爬虫实现，跳过。")
                continue

            crawler_instance = crawler_cls()
            platform_upper = p_name.upper()
            target_user = getattr(config, f"{platform_upper}_TARGET_USER", None)

            crawl_tasks.append(crawler_instance.crawl(target_user=target_user))
            active_crawler_instances.append(crawler_instance)
            platform_names.append(p_name)

        if not crawl_tasks:
            return "", 0, None, []

        real_results = await asyncio.gather(*crawl_tasks)

        # 2. 第二步：处理每个平台的结果，并根据平台配置判断是否需要“无中生有”
        platform_reports = []

        for i, (p_name, crawler_instance) in enumerate(
            zip(platform_names, active_crawler_instances)
        ):
            activities_map = real_results[i]

            # 生成该平台的真实报告
            real_report_part, real_count = crawler_instance.generate_report(
                activities_map
            )
            total_real_count += real_count

            # 获取该平台的伪装配置
            source_cfg = config.get(f"crawler_sources.{p_name}", {})
            camou_cfg = source_cfg.get("camouflage", {})

            # 判断是否触发伪装
            # 判断是否触发伪装 (包含等于的情况)
            if camou_cfg.get("enabled", False) and real_count <= camou_cfg.get(
                "threshold", 0
            ):
                max_items = camou_cfg.get("max_items", 0)
                needed = max_items - real_count

                if needed > 0:
                    logger.info(
                        f"🎭 [伪装] 平台 {p_name} 真实记录({real_count})低于阈值，准备补全至 {max_items} 条..."
                    )

                    platform_upper = p_name.upper()
                    target_user = getattr(config, f"{platform_upper}_TARGET_USER", None)

                    try:
                        fake_items = await crawler_instance.generate_camouflage_data(
                            needed,
                            target_user=target_user,
                            lookback_days=camou_cfg.get("lookback_days", 14),
                            cooldown_days=camou_cfg.get("cooldown_days", 10),
                        )

                        if fake_items:
                            # 构造伪装报告部分（直接对齐 generate_report 的格式）
                            fake_report_part = (
                                f"\n  🎭 [待伪装素材 - {p_name.upper()}]\n"
                            )
                            # 按 source 和 date 进行嵌套分组显示
                            source_date_grouped = defaultdict(lambda: defaultdict(list))
                            for item in fake_items:
                                # 包含名称和路径，增加辨识度
                                full_source = f"{item.source} ({item.repo_path})"
                                item_date = item.date or "未知日期"
                                source_date_grouped[full_source][item_date].append(item)
                                fake_items_used.append(item)

                            # 排序并生成三层结构的报告
                            sorted_sources = sorted(source_date_grouped.keys())
                            for source_label in sorted_sources:
                                fake_report_part += f"    数据源: {source_label}\n"
                                date_map = source_date_grouped[source_label]
                                for date_str in sorted(date_map.keys(), reverse=True):
                                    fake_report_part += f"      📅 日期: {date_str}\n"
                                    for item in date_map[date_str]:
                                        fake_report_part += (
                                            f"        - {item.content}\n"
                                        )

                            real_report_part += fake_report_part
                            has_camouflage_triggered = True
                        else:
                            logger.warning(
                                f"🎭 [伪装] 平台 {p_name} 未能提取到足够的历史素材。"
                            )
                    except Exception as e:
                        logger.error(f"❌ [伪装] 平台 {p_name} 提取伪装数据失败: {e}")

            if real_report_part.strip():
                platform_reports.append(real_report_part)

        # 合并所有报告
        if platform_reports:
            report_text = "".join(platform_reports)
            # 全局包裹容器
            if total_real_count > 0:
                # 重新在头部插入全局标识（如果存在真实记录）
                report_text = f"\n  📦 [今日真实工作]\n" + report_text

        # 3. 第三步：采集各平台的额外报告（人工补充的 Markdown 文件）
        for crawler_name in self._registry:
            crawler_cls = self._registry[crawler_name]
            # 延迟实例化
            crawler_instance = crawler_cls()
            # 检查爬虫是否实现了 extra_report 能力
            if not hasattr(crawler_instance, "fetch_extra_report"):
                continue

            extra_result = await crawler_instance.fetch_extra_report()
            if not extra_result:
                continue

            extra_text, extra_count = crawler_instance.generate_extra_report(
                extra_result
            )
            if extra_text.strip():
                report_text += extra_text
                total_real_count += extra_count
                # 采集后立即归档清理
                crawler_instance.archive_extra_report()
                logger.info(
                    f"📝 [额外报告] 平台 {crawler_name} 已合并 {extra_count} 条额外补充内容"
                )

        return report_text, total_real_count, has_camouflage_triggered, fake_items_used


# 单例
crawler_manager = CrawlerManager()
