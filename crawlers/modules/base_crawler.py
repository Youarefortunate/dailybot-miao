import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from loguru import logger
from .crawler_manager import crawler_manager

# 东八区时区
_TZ = timezone(timedelta(hours=8))


class BaseCrawler(ABC):
    """
    通用数据爬虫基类，采用模板方法模式定义标准采集流程。
    """

    CRAWLER_NAME = "unknown"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 自动将子类注册到爬虫管理器
        if cls.CRAWLER_NAME != "unknown":
            crawler_manager.register_crawler(cls.CRAWLER_NAME, cls)

    def __init__(self):
        pass

    def get_platform_name(self) -> str:
        """
        获取平台显示名称（默认优先使用类定义的 CRAWLER_NAME）
        """
        return self.CRAWLER_NAME

    @abstractmethod
    def get_sources_config(self) -> list:
        """
        获取当前平台的数据实体（如仓库、项目、任务看板等）配置列表
        """
        pass

    @abstractmethod
    async def fetch_activities(
        self, entity_config: dict, since: str, until: str
    ) -> list:
        """
        调用平台 API 获取原始活动（Activity）列表
        :param entity_config: 数据实体配置字典 (例如包含 path, branch 等)
        """
        pass

    @abstractmethod
    def extract_activity_data(self, raw_data: dict) -> dict:
        """
        提取原始数据为统一的格式:
        {
            "id": str,
            "author_name": str,
            "author_email": str,
            "content": str,
            "created_at": str (ISO 格式),
            "metadata": dict (可选，如分支名、状态等)
        }
        """
        pass

    def format_activity(self, activity_data: dict) -> str:
        """
        将结构化的活动数据格式化为最终显示的文本
        子类可以重写此方法以定制展示风格（如 Git 分支显示或 Bug 状态显示）
        """
        time_display = activity_data.get("time_display", "")
        content = activity_data.get("content", "")
        time_str = f"[{time_display}]" if time_display else ""
        return f"{time_str} {content}".strip()

    def should_skip_activity(self, activity_data: dict) -> bool:
        """
        通用的活动过滤逻辑，默认处理常见 Git 忽略项，子类可以重写此方法以定制过滤逻辑
        """
        content = activity_data.get("content", "")
        if not content:
            return True

        content_clean = content.lower().strip()

        # 常见 Git 忽略项，保留以兼容代码型历史仓库
        if content_clean.startswith("merge branch") or content_clean.startswith(
            "merge remote-tracking branch"
        ):
            return True

        prefixes = ["chore:", "feat:", "fix:"]
        matched_prefix = next(
            (p for p in prefixes if content_clean.startswith(p)), None
        )

        if matched_prefix:
            ctx = content_clean[len(matched_prefix) :].strip()
            if not ctx or ctx == matched_prefix[:-1]:
                return True
        elif content_clean in ["chore", "feat", "fix", "chore:", "feat:", "fix:"]:
            return True

        return False

    def _parse_crawl_dates(self, crawl_dates=None):
        """
        解析爬取日期配置，返回 (since, until) 元组列表。
        """
        if not crawl_dates:
            # 默认爬取当天
            now = datetime.now(_TZ)
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
            until = now.replace(hour=23, minute=59, second=59, microsecond=0)
            return [(since.isoformat(), until.isoformat())]

        ranges = []
        for date_segment in crawl_dates:
            parts = [p.strip() for p in date_segment.split(",") if p.strip()]

            if len(parts) == 1:
                # 单个日期
                try:
                    d = datetime.strptime(parts[0], "%Y-%m-%d").replace(tzinfo=_TZ)
                    since = d.replace(hour=0, minute=0, second=0, microsecond=0)
                    until = d.replace(hour=23, minute=59, second=59, microsecond=0)
                    ranges.append((since.isoformat(), until.isoformat()))
                except ValueError:
                    logger.warning(f"日期格式错误: {parts[0]}")
            elif len(parts) == 2:
                # 日期区间
                try:
                    d_start = datetime.strptime(parts[0], "%Y-%m-%d").replace(
                        tzinfo=_TZ
                    )
                    d_end = datetime.strptime(parts[1], "%Y-%m-%d").replace(tzinfo=_TZ)
                    since = d_start.replace(hour=0, minute=0, second=0, microsecond=0)
                    until = d_end.replace(hour=23, minute=59, second=59, microsecond=0)
                    ranges.append((since.isoformat(), until.isoformat()))
                except ValueError:
                    logger.warning(f"日期区间格式错误: {parts[0]}, {parts[1]}")
            else:
                logger.warning(f"无法解析日期配置: {date_segment}，已跳过")

        return ranges

    def _format_date_range(self, since, until):
        """
        格式化日期范围显示
        """
        s = since[:10]
        u = until[:10]
        return s if s == u else f"{s}~{u}"

    async def crawl(self, target_user=None) -> dict:
        """
        模板方法：定义爬取的标准流程 (异步并行化)
        """
        all_activities = {}
        platform_name = self.get_platform_name()
        sources_config = self.get_sources_config()

        if not sources_config:
            logger.info(f"🚢 平台 {platform_name} 未发现任何数据实体配置，跳过采集。")
            return all_activities

        # 平台级别去重 (避免同一 Activity ID 重复采集)
        seen_ids = set()

        # 构造并发任务列表
        async def crawl_entity(entity):
            entity_path = entity.get("path") or entity.get("id") or "Unknown"
            entity_name = entity.get("name")
            date_ranges = self._parse_crawl_dates(entity.get("crawl_dates"))

            entity_grouped = {}

            for since, until in date_ranges:
                date_label = self._format_date_range(since, until)
                logger.opt(colors=True).info(
                    f"🔍 正在从 <cyan>{platform_name}</cyan> 采集: <magenta>{entity_path}</magenta> "
                    f"(日期范围: <fg #87CEEB>{date_label}</fg #87CEEB>)"
                )

                try:
                    # 子类需全权处理特定于该平台的并发和请求细节（如 Git 分支轮循）
                    raw_items = await self.fetch_activities(entity, since, until)
                    if not raw_items or not isinstance(raw_items, list):
                        continue

                    for item in raw_items:
                        activity_data = self.extract_activity_data(item)
                        activity_id = activity_data.get("id")

                        # 去重逻辑
                        if not activity_id or activity_id in seen_ids:
                            continue

                        # 过滤逻辑
                        if self.should_skip_activity(activity_data):
                            continue

                        # 用户过滤逻辑
                        author_name = activity_data.get("author_name", "")
                        author_email = activity_data.get("author_email", "")
                        if target_user:
                            u_f = target_user.lower()
                            if (
                                u_f not in author_name.lower()
                                and u_f not in author_email.lower()
                            ):
                                continue

                        # 确定日期分组键和显示时间
                        created_at = activity_data.get("created_at", "")
                        date_key, time_display = "未知日期", ""
                        if created_at:
                            try:
                                t_obj = datetime.fromisoformat(
                                    created_at.replace("Z", "+00:00")
                                ).astimezone(_TZ)
                                date_key = t_obj.strftime("%Y-%m-%d")
                                time_display = t_obj.strftime("%H:%M")
                            except:
                                pass

                        seen_ids.add(activity_id)

                        # 把时间格式也塞给 activity_data
                        activity_data["time_display"] = time_display

                        # 格式化展示文本
                        formatted_msg = self.format_activity(activity_data)
                        if formatted_msg:
                            entity_grouped.setdefault(date_key, []).append(
                                formatted_msg
                            )
                except Exception as e:
                    logger.opt(colors=True).error(
                        f"采集 <magenta>{entity_path}</magenta> 失败: {e}"
                    )

            return entity_path, entity_name, entity_grouped

        # 并发执行所有实体的采集
        results = await asyncio.gather(
            *(crawl_entity(entity) for entity in sources_config)
        )

        for entity_path, entity_alias, grouped in results:
            if grouped:
                display_name = (
                    f"{entity_path} ({entity_alias})" if entity_alias else entity_path
                )

                if display_name not in all_activities:
                    all_activities[display_name] = {}

                for date_key, msgs in grouped.items():
                    all_activities[display_name].setdefault(date_key, []).extend(msgs)

                count = sum(len(msgs) for msgs in grouped.values())
                logger.opt(colors=True).info(
                    f"数据源 <magenta>{entity_path}</magenta> 找到 <red>{count}</red> 条新活动记录"
                )

        return all_activities

    def generate_report(self, activities_map: dict) -> tuple[str, int]:
        """
        根据采集到的活动数据（结构化字典），生成平台专属的汇报文本组合。
        子类可重写此方法以定制平台的整个汇报排版（例如更改“数据源”为特定平台词汇）。
        """
        platform_name = self.get_platform_name().upper()
        platform_report = f"\n  平台: {platform_name}\n"
        total_count = 0

        for entity_name, date_groups in activities_map.items():
            platform_report += f"    数据源: {entity_name}\n"
            for date_str in sorted(date_groups.keys(), reverse=True):
                platform_report += f"      📅 日期: {date_str}\n"
                for msg in date_groups[date_str]:
                    platform_report += f"        - {msg}\n"
                    total_count += 1

        return platform_report, total_count
