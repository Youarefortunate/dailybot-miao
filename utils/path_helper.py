import os
import sys
from datetime import datetime, timezone, timedelta


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


def resolve_path(relative_path: str, base_dir: str = None) -> str:
    """
    解析文件路径，转换为绝对路径。
    - 如果是绝对路径，直接返回
    - 如果是相对路径，基于 base_dir（默认为 app_dir）解析

    :param relative_path: 相对路径或绝对路径
    :param base_dir: 基础目录，默认为程序运行目录
    :return: 绝对路径
    """
    if os.path.isabs(relative_path):
        return os.path.normpath(relative_path)

    if base_dir is None:
        base_dir = get_app_dir()

    return os.path.normpath(os.path.join(base_dir, relative_path))


def ensure_dir(path: str) -> str:
    """
    确保目录存在，如果不存在则创建。

    :param path: 目录路径
    :return: 传入的目录路径
    """
    os.makedirs(path, exist_ok=True)
    return path


def read_file(file_path: str, encoding: str = "utf-8") -> str:
    """
    读取文件内容。

    :param file_path: 文件路径
    :param encoding: 文件编码，默认 utf-8
    :return: 文件内容，文件不存在或读取失败返回空字符串
    """
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    except Exception:
        return ""


def write_file(file_path: str, content: str, encoding: str = "utf-8") -> bool:
    """
    写入内容到文件。

    :param file_path: 文件路径
    :param content: 要写入的内容
    :param encoding: 文件编码，默认 utf-8
    :return: 是否成功
    """
    try:
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
        return True
    except Exception:
        return False


def append_file(file_path: str, content: str, encoding: str = "utf-8") -> bool:
    """
    追加内容到文件。

    :param file_path: 文件路径
    :param content: 要追加的内容
    :param encoding: 文件编码，默认 utf-8
    :return: 是否成功
    """
    try:
        ensure_dir(os.path.dirname(file_path))
        with open(file_path, "a", encoding=encoding) as f:
            f.write(content)
        return True
    except Exception:
        return False


def file_exists(file_path: str) -> bool:
    """
    检查文件是否存在。

    :param file_path: 文件路径
    :return: 是否存在
    """
    return os.path.exists(file_path)


def cleanup_old_files(
    directory: str, extension: str, days: int, date_format: str = "%Y-%m-%d"
) -> int:
    """
    清理目录中过期的文件（根据文件名中的日期判断）。

    :param directory: 目录路径
    :param extension: 文件扩展名（如 .md, .log）
    :param days: 保留天数，超过此天数的文件将被删除
    :param date_format: 文件名中的日期格式，默认 %Y-%m-%d
    :return: 删除的文件数量
    """
    if not os.path.exists(directory):
        return 0

    now = datetime.now()
    deleted_count = 0

    try:
        for filename in os.listdir(directory):
            if not filename.endswith(extension):
                continue

            file_path = os.path.join(directory, filename)
            date_str = filename[: -len(extension)]

            try:
                file_date = datetime.strptime(date_str, date_format)
                age_days = (now - file_date).days

                if age_days > days:
                    os.remove(file_path)
                    deleted_count += 1
            except ValueError:
                continue
    except Exception:
        pass

    return deleted_count
