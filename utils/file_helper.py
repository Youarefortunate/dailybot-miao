import json
import os
from loguru import logger


def read_json(file_path: str, default=None):
    """
    读取 JSON 文件内容。
    """
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取文件 {file_path} 失败: {e}")
        return default


def write_json(file_path: str, data: any, indent: int = 2):
    """
    将数据写入 JSON 文件。
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception as e:
        logger.error(f"写入文件 {file_path} 失败: {e}")
        return False
