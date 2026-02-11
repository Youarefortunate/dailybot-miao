import urllib.parse
from datetime import datetime, timezone, timedelta
from loguru import logger
from api import apis
from request.hooks.use_request import use_request
from config import config

# 东八区时区
_TZ = timezone(timedelta(hours=8))


class GitlabCrawler:
    """
    GitLab 提交记录爬虫
    """

    def __init__(self):
        self.gitlab_api = use_request(apis.repo_gitlab.get_commits)

    def _parse_crawl_dates(self, crawl_dates=None):
        """
        解析爬取日期配置，返回 (since, until) 元组列表。
        :param crawl_dates: 日期配置列表，不传则默认爬取当天 (00:00 ~ 23:59:59)
            - 单个日期 "2026-02-10": 爬取指定那天
            - 日期区间 "2026-02-08, 2026-02-10": 爬取指定日期区间
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
                # 单个日期：爬取该天全天
                d = datetime.strptime(parts[0], "%Y-%m-%d").replace(tzinfo=_TZ)
                since = d.replace(hour=0, minute=0, second=0, microsecond=0)
                until = d.replace(hour=23, minute=59, second=59, microsecond=0)
                ranges.append((since.isoformat(), until.isoformat()))
            elif len(parts) == 2:
                # 日期区间：从起始日期 00:00 到结束日期 23:59:59
                d_start = datetime.strptime(parts[0], "%Y-%m-%d").replace(tzinfo=_TZ)
                d_end = datetime.strptime(parts[1], "%Y-%m-%d").replace(tzinfo=_TZ)
                since = d_start.replace(hour=0, minute=0, second=0, microsecond=0)
                until = d_end.replace(hour=23, minute=59, second=59, microsecond=0)
                ranges.append((since.isoformat(), until.isoformat()))
            else:
                logger.warning(f"无法解析日期配置: {date_segment}，已跳过")

        return ranges

    def get_today_commits(self, target_user=None):
        """
        爬取所有配置仓库中指定用户的提交记录
        :param target_user: 指定用户（邮箱或用户名关键词），若不传则使用全局配置
        """
        all_commits = {}

        user_to_filter = target_user or config.GITLAB_TARGET_USER

        for repo in config.GITLAB_REPOS:
            repo_path = repo["path"]
            branch_raw = repo.get("branch", "master")
            repo_name = repo_path.split("/")[-1]

            # 支持逗号分隔的多分支配置，例如 "test, master"
            branches = [b.strip() for b in branch_raw.split(",") if b.strip()]

            # 解析该仓库的日期配置
            crawl_dates = repo.get("crawl_dates", None)
            date_ranges = self._parse_crawl_dates(crawl_dates)
            date_labels = [self._format_date_range(s, u) for s, u in date_ranges]

            # GitLab API 要求项目路径必须经过 URL 编码
            encoded_path = urllib.parse.quote_plus(repo_path)

            # 用于去重（同一个 commit 可能存在于多个分支或时间段）
            seen_ids = set()
            filtered_messages = []

            for branch in branches:
                for since, until in date_ranges:
                    date_label = self._format_date_range(since, until)
                    logger.opt(colors=True).info(
                        f"📅 正在爬取仓库: <magenta>{repo_path}</magenta> "
                        f"(分支: <yellow>{branch}</yellow>, 日期: <fg #87CEEB>{date_label}</fg>)"
                    )

                    try:
                        res_data = self.gitlab_api.fetch(
                            {
                                "project_id": encoded_path,
                                "ref_name": branch,
                                "since": since,
                                "until": until,
                            }
                        )

                        if not res_data or not isinstance(res_data, list):
                            logger.opt(colors=True).info(
                                f"仓库 <magenta>{repo_name}</magenta> "
                                f"(分支: <yellow>{branch}</yellow>) 该时段无提交或返回异常"
                            )
                            continue

                        # 过滤并提取提交记录
                        for commit in res_data:
                            commit_id = commit.get("id", "")
                            if commit_id in seen_ids:
                                continue
                            seen_ids.add(commit_id)

                            author_name = commit.get("author_name", "")
                            author_email = commit.get("author_email", "")
                            message = commit.get("title", "")

                            # 如果指定了过滤用户
                            if user_to_filter:
                                u_f = user_to_filter.lower()
                                if (
                                    u_f not in author_name.lower()
                                    and u_f not in author_email.lower()
                                ):
                                    continue

                            filtered_messages.append(message)

                    except Exception as e:
                        logger.opt(colors=True).error(
                            f"爬取仓库 <magenta>{repo_path}</magenta> (分支: <yellow>{branch}</yellow>) 失败: {e}"
                        )

            if filtered_messages:
                all_commits[repo_name] = filtered_messages
                logger.opt(colors=True).info(
                    f"仓库 <magenta>{repo_name}</magenta> 找到 <green>{len(filtered_messages)}</green> 条符合条件的提交"
                )

        return all_commits

    @staticmethod
    def _format_date_range(since, until):
        """
        格式化日期范围显示：单日只显示日期，区间显示 起始~结束
        """
        s = since[:10]
        u = until[:10]
        return s if s == u else f"{s}~{u}"
