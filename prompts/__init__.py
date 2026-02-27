import os
from request.core.dot_dict import DotDict
from utils.path_helper import get_resource_path

# 存储全局提示词定义
prompts = DotDict()


def _load_prompts():
    """
    递归加载 prompts 目录下的所有 .md 文件并映射为点号访问结构
    """

    current_dir = get_resource_path("prompts")

    def _walk_dir(path, current_dict):
        if not os.path.exists(path):
            return

        for item in os.listdir(path):
            # 忽略隐藏文件、系统生成文件
            if item.startswith(".") or item.startswith("__"):
                continue

            item_path = os.path.join(path, item)

            if os.path.isdir(item_path):
                # 文件夹映射为 DotDict 节点以便级联点号访问
                sub_dict = DotDict()
                current_dict[item] = sub_dict
                _walk_dir(item_path, sub_dict)
            elif item.endswith(".md"):
                # .md 文件内容直接读取为字符串值
                key = item[:-3]
                try:
                    with open(item_path, "r", encoding="utf-8") as f:
                        current_dict[key] = f.read().strip()
                except Exception:
                    pass

    _walk_dir(current_dir, prompts)


# 执行加载
_load_prompts()

__all__ = ["prompts"]
