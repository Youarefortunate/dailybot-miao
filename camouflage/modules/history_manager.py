from datetime import datetime, timezone, timedelta
from typing import Dict, List
from .models import CamouflageHistory
from utils.file_helper import read_json, write_json
from loguru import logger

_TZ = timezone(timedelta(hours=8))


class HistoryManager:
    """
    负责管理伪装素材的使用历史与 LRU 冷却逻辑
    """

    def __init__(self, history_file: str = "camouflage_history.json"):
        self.history_file = history_file
        self.history: Dict[str, CamouflageHistory] = {}
        self.load()

    def load(self):
        """
        加载历史记录
        """
        data = read_json(self.history_file, {})
        for k, v in data.items():
            try:
                self.history[k] = CamouflageHistory(**v)
            except Exception as e:
                logger.warning(f"解析历史记录项 {k} 失败: {e}")

    def save(self):
        """
        保存历史记录
        """
        data = {k: v.dict() for k, v in self.history.items()}
        write_json(self.history_file, data)

    def is_in_cooldown(self, item_id: str, cooldown_days: int) -> bool:
        """
        检查素材是否处于冷却期
        """
        if item_id not in self.history:
            return False

        last_used_str = self.history[item_id].last_used
        try:
            last_used = datetime.strptime(last_used_str, "%Y-%m-%d").replace(tzinfo=_TZ)
            diff = datetime.now(_TZ) - last_used
            return diff.days < cooldown_days
        except Exception:
            return False

    def update_usage(self, item_id: str, variant: str):
        """
        更新素材的使用记录
        """
        now_str = datetime.now(_TZ).strftime("%Y-%m-%d")
        if item_id in self.history:
            self.history[item_id].last_used = now_str
            if variant not in self.history[item_id].variants:
                self.history[item_id].variants.append(variant)
        else:
            self.history[item_id] = CamouflageHistory(
                last_used=now_str, variants=[variant]
            )
        self.save()

    def get_variants(self, item_id: str) -> List[str]:
        """
        获取素材已生成的变体
        """
        if item_id in self.history:
            return self.history[item_id].variants
        return []
