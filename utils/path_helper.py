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


def get_app_dir() -> str:
    """
    获取程序运行的真实物理目录。
    - 打包环境下：返回 .exe 所在的文件夹。
    - 源码环境下：返回当前工作目录。
    用于访问外部配置文件 (.env, config.yaml) 和写入日志/锁文件。
    """
    if getattr(sys, "frozen", False):
        # sys.executable 是 .exe 的完整路径
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(".")


def get_root_path() -> str:
    """
    获取项目资源根目录路径 (适配打包)
    """
    return get_resource_path("")
