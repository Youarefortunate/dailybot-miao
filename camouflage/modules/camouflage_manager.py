import asyncio
import random
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from .models import CamouflageItem
from .history_manager import HistoryManager
from common.config import config
from loguru import logger
from utils.dynamic_manager import BaseDynamicManager

_TZ = timezone(timedelta(hours=8))


class CamouflageManager(BaseDynamicManager):
    """
    伪装功能核心调度器，负责采集原始素材供最终 AI 总结节点使用。
    """

    def __init__(self):
        impl_dir = os.path.join("camouflage", "impl")
        super().__init__(
            impl_dir_path=impl_dir,
            module_prefix="camouflage.impl",
            name_templates=["{key}_provider", "{key}"],
        )

        self.history = HistoryManager()
        self.cfg = config.get("camouflage", {})
        self.is_enabled = self.cfg.get("enabled", False)

    async def _get_all_provider_items(self) -> List[CamouflageItem]:
        """
        并发从所有已发现的提供者中采集素材。
        """
        lookback_days = self.cfg.get("lookback_days", 14)
        now = datetime.now(_TZ)
        since = (
            (now - timedelta(days=lookback_days))
            .replace(hour=0, minute=0, second=0)
            .isoformat()
        )
        until = (
            (now - timedelta(days=1)).replace(hour=23, minute=59, second=59).isoformat()
        )

        # 获取所有已注册的提供者标识
        keys = self.get_all_keys()

        all_items = []
        tasks = []
        for key in keys:
            provider_cls = self.get_class(key)
            if provider_cls:
                provider_inst = provider_cls()
                tasks.append(provider_inst.fetch_items(since, until))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks)
        for items in results:
            all_items.extend(items)

        return all_items

    async def generate_fake_reports(
        self, needed_count: int
    ) -> Dict[str, List[CamouflageItem]]:
        """
        提供原始伪装素材列表
        """
        if not self.is_enabled or needed_count <= 0:
            return {}

        max_items = self.cfg.get("max_items", 5)
        count_to_gen = min(needed_count, max_items)
        cooldown_days = self.cfg.get("cooldown_days", 10)

        # 1. 采集历史素材
        all_items = await self._get_all_provider_items()
        if not all_items:
            logger.info("📭 无素材提供者或无历史记录。")
            return {}

        # 2. 冷却控制 (LRU)
        available_items = [
            item
            for item in all_items
            if not self.history.is_in_cooldown(item.id, cooldown_days)
        ]

        if not available_items:
            logger.info("⏳ 今日素材均在冷却期。")
            return {}

        # 3. 均衡选择策略
        random.shuffle(available_items)
        selected_items: List[CamouflageItem] = []
        source_counts = {}

        while len(selected_items) < count_to_gen and available_items:
            for item in list(available_items):
                if len(selected_items) >= count_to_gen:
                    break
                if source_counts.get(item.source, 0) <= min(
                    source_counts.values() or [0]
                ):
                    selected_items.append(item)
                    source_counts[item.source] = source_counts.get(item.source, 0) + 1
                    available_items.remove(item)

        # 4. 组装返回原始数据 (记录已使用历史需在最终 AI 总结成功后进行，此处仅记录 item_id)
        # 为保持逻辑简单，我们在这里先记录使用轨迹（假设最终 AI 会生成）
        fake_data = {}
        for item in selected_items:
            fake_data.setdefault(item.source, []).append(item)
            # 注意：此次不在此处更新 history.update_usage，因为尚未生成具体变体
            # 但为了防止本次运行中重复挑选，我们标记 item 为“待使用”
            # 由于此处是单次运行流程，selected_items 已经去重，所以暂时无需额外标记

        return fake_data


# 单例导出
camouflage_manager = CamouflageManager()
