from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from loguru import logger
from .crawler_manager import crawler_manager

# 东八区时区
_TZ = timezone(timedelta(hours=8))


class BaseCrawler(ABC):
    """
    爬虫基类，采用模板方法模式定义爬取流程。
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
    def get_repos_config(self) -> list:
        """
        获取当前平台的仓库配置列表
        """
        pass

    @abstractmethod
    def fetch_repo_commits(
        self, repo_path: str, branch: str, since: str, until: str
    ) -> list:
        """
        执行具体的 API 请求，获取提交记录列表
        """
        pass

    @abstractmethod
    def _extract_commit_data(self, commit: dict) -> dict:
        """
        从原始 commit 数据中提取统一格式的数据
        返回格式: {
            "id": str,
            "author_name": str,
            "author_email": str,
            "message": str,
            "created_at": str (ISO 格式)
        }
        """
        pass

    def _should_skip_commit(self, commit_data: dict) -> bool:
        """
        通用的提交记录过滤逻辑
        """
        message = commit_data.get("message", "")
        # 1. 过滤：忽略 Merge 分支记录
        if message.startswith("Merge branch") or message.startswith(
            "Merge remote-tracking branch"
        ):
            return True

        # 2. 过滤：忽略无意义的短提交 (如 chore: chore, feat: feat, chore: , feat: )
        msg_clean = message.lower().strip()
        prefixes = ["chore:", "feat:", "fix:"]
        matched_prefix = next((p for p in prefixes if msg_clean.startswith(p)), None)

        if matched_prefix:
            # 提取前缀后的内容
            content = msg_clean[len(matched_prefix) :].strip()
            # 如果内容为空，或者内容与前缀标识名相同 (如 chore: chore)，则过滤
            if not content or content == matched_prefix[:-1]:
                return True
        elif msg_clean in [
            "chore",
            "feat",
            "fix",
            "chore:",
            "feat:",
            "fix:",
        ]:
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

    def crawl(self, target_user=None) -> dict:
        """
        模板方法：定义爬取的标准流程
        """
        all_commits = {}
        platform_name = self.get_platform_name()
        repos_config = self.get_repos_config()

        if not repos_config:
            logger.info(f"Ø 平台 {platform_name} 未配置任何仓库，跳过。")
            return all_commits

        for repo in repos_config:
            repo_path = repo["path"]
            branch_raw = repo.get("branch", "master")
            repo_name = repo_path.split("/")[-1]

            # 支持多分支
            branches = [b.strip() for b in branch_raw.split(",") if b.strip()]

            # 解析日期配置
            crawl_dates = repo.get("crawl_dates", None)
            date_ranges = self._parse_crawl_dates(crawl_dates)

            # 用于去重
            seen_ids = set()
            grouped_messages = {}

            for branch in branches:
                for since, until in date_ranges:
                    date_label = self._format_date_range(since, until)
                    logger.opt(colors=True).info(
                        f"📅 正在从 <cyan>{platform_name}</cyan> 爬取仓库: <magenta>{repo_path}</magenta> "
                        f"(分支: <yellow>{branch}</yellow>, 日期: <fg #87CEEB>{date_label}</fg #87CEEB>)"
                    )

                    try:
                        raw_commits = self.fetch_repo_commits(
                            repo_path, branch, since, until
                        )
                        if not raw_commits or not isinstance(raw_commits, list):
                            continue

                        for raw_commit in raw_commits:
                            commit_data = self._extract_commit_data(raw_commit)
                            commit_id = commit_data.get("id")

                            if not commit_id or commit_id in seen_ids:
                                continue

                            # 过滤逻辑
                            if self._should_skip_commit(commit_data):
                                continue

                            # 用户过滤
                            author_name = commit_data.get("author_name", "")
                            author_email = commit_data.get("author_email", "")
                            if target_user:
                                u_f = target_user.lower()
                                if (
                                    u_f not in author_name.lower()
                                    and u_f not in author_email.lower()
                                ):
                                    continue

                            # 时间处理与分组
                            created_at = commit_data.get("created_at", "")
                            date_key = "未知日期"
                            time_display = ""
                            if created_at:
                                try:
                                    # 兼容不同平台的 ISO 格式或直接解析
                                    t_obj = datetime.fromisoformat(
                                        created_at.replace("Z", "+00:00")
                                    ).astimezone(_TZ)
                                    date_key = t_obj.strftime("%Y-%m-%d")
                                    time_display = t_obj.strftime("%Y-%m-%d %H:%M")
                                except Exception:
                                    pass

                            message = commit_data.get("message", "")
                            seen_ids.add(commit_id)
                            grouped_messages.setdefault(date_key, []).append(
                                f"[{time_display}] {message}"
                            )

                    except Exception as e:
                        logger.opt(colors=True).error(
                            f"爬取 <magenta>{repo_path}</magenta> 失败: {e}"
                        )

            if grouped_messages:
                # 获取仓库别名（项目名）
                repo_alias = repo.get("name")
                display_name = (
                    f"{repo_path} ({repo_alias})" if repo_alias else repo_path
                )
                all_commits[display_name] = grouped_messages

                count = sum(len(msgs) for msgs in grouped_messages.values())
                logger.opt(colors=True).info(
                    f"仓库 <magenta>{repo_path}</magenta> 找到 <red>{count}</red> 条符合条件的提交"
                )

        return all_commits
