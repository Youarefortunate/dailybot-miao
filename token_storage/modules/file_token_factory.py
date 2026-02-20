import json
import os
import asyncio
from threading import RLock
from typing import Optional, Any, Dict
from loguru import logger
from common.config import config


class FileTokenFactory:
    """
    Token 文件存储工厂
    专注于 token.json 的读写与并发控制
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._data: Dict[str, Any] = {}
        self._lock = RLock()
        self._async_lock = asyncio.Lock()  # 异步协程锁
        self.load()

    def load(self):
        """从文件加载数据到内存"""
        if not os.path.exists(self.file_path):
            return
        with self._lock:
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self._data = json.loads(content)
            except Exception as e:
                logger.error(f"加载 Token 文件 {self.file_path} 失败: {e}")

    def save(self, data: Optional[Dict[str, Any]] = None):
        """将数据持久化到文件，依据 config.ENABLED_WORKFLOWS 进行过滤"""
        with self._lock:
            if data is not None:
                self._data.update(data)

            enabled_workflows = getattr(config, "ENABLED_WORKFLOWS", [])
            save_data = {}
            for platform in enabled_workflows:
                platform_key = platform.lower()
                if platform_key in self._data:
                    save_data[platform_key] = self._data[platform_key]

            try:
                os.makedirs(
                    os.path.dirname(os.path.abspath(self.file_path)), exist_ok=True
                )
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"保存 Token 文件失败: {e}")

    def get_platform_data(self, platform: str) -> Dict[str, Any]:
        """获取指定平台的数据副本"""
        with self._lock:
            platform_key = platform.lower()
            return self._data.get(platform_key, {}).copy()

    def get_all(self) -> Dict[str, Any]:
        """获取所有平台的数据副本"""
        with self._lock:
            return self._data.copy()

    async def set_platform_entry(self, platform: str, key: str, value: Any):
        """设置某个平台的单条条目并触发保存"""
        async with self._async_lock:
            with self._lock:
                platform_key = platform.lower()
                if platform_key in self._data:
                    # 合并逻辑：如果已存在，则合并内部字段
                    if isinstance(
                        self._data[platform_key].get(key), dict
                    ) and isinstance(value, dict):
                        self._data[platform_key][key].update(value)
                    else:
                        self._data[platform_key][key] = value
                else:
                    self._data[platform_key] = {key: value}

            # 持久化也需要改造成异步/线程安全
            # 重要：必须在释放 self._lock 后再执行，否则 to_thread 里的 save 会产生死锁
            await asyncio.to_thread(self.save)
