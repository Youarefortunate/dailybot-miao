import os
import sys


def get_resource_path(relative_path: str) -> str:
    """
    获取资源的绝对路径。适配源码运行和 PyInstaller 打包运行。

    :param relative_path: 相对路径 (以项目根目录为起点)
    :return: 绝对路径
    """
    # PyInstaller 打包后的临时解压目录
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))

    return os.path.normpath(os.path.join(base_path, relative_path))


def get_root_path() -> str:
    """
    获取项目根目录路径
    """
    return get_resource_path("")
