import threading
import inspect
import asyncio
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, Union
import lark_oapi as lark
from common.config import Config

T = TypeVar("T", bound=Callable[..., Any])

DEFAULT_CLIENT_CONFIG = {
    "domain": lark.FEISHU_DOMAIN,
    "timeout": 3,
    "log_level": lark.LogLevel.ERROR,
}


def _build_client(config: dict) -> lark.Client:
    """
    构建飞书 Client
    动态透传 builder 参数
    """
    builder = lark.Client.builder()

    for key, value in config.items():
        if value is None:
            continue
        # 严格检查 builder 是否有该方法且可调用
        attr = getattr(builder, key, None)
        if attr and callable(attr):
            attr(value)

    return builder.build()


_client_cache: Dict[tuple, lark.Client] = {}
_cache_lock = threading.Lock()


def _get_cached_client(config: dict) -> lark.Client:
    """
    根据配置生成唯一 key，缓存 client
    """
    # 过滤掉 None 值并排序生成 key
    clean_config = {k: v for k, v in config.items() if v is not None}
    key = tuple(sorted(clean_config.items()))

    if key in _client_cache:
        return _client_cache[key]

    with _cache_lock:
        if key not in _client_cache:
            _client_cache[key] = _build_client(clean_config)

    return _client_cache[key]


class with_lark_client:
    """
    自动注入飞书 Client 的装饰器 (类实现)。

    支持同步和异步函数。自动从全局 Config 加载 FEISHU_APP_ID 和 FEISHU_APP_SECRET。

    用法示例：
        @with_lark_client()  # 默认注入参数名为 "client"
        def foo(client): ...

        @with_lark_client("lark")  # 注入参数名为 "lark"
        async def bar(lark): ...

        @with_lark_client(timeout=10)  # 配置参数
        def baz(client): ...

        @with_lark_client({"timeout": 10}, inject_as="lark") # 混合使用
        def qux(lark): ...
    """

    def __init__(self, *args, **kwargs):
        """
        初始化装饰器参数。

        Args:
            *args:
                - 如果第一个参数是 str，则为 inject_as。
                - 如果第一个参数是 dict，则为 override_config。
            **kwargs: 额外的配置参数。如果存在 inject_as，则从 kwargs 中提取并移除。
        """
        self.inject_as = "client"
        self.override_config = {}

        # 处理位置参数
        if args:
            first_arg = args[0]
            if isinstance(first_arg, str):
                self.inject_as = first_arg
            elif isinstance(first_arg, dict):
                self.override_config.update(first_arg)

        # 处理关键字参数
        if "inject_as" in kwargs:
            self.inject_as = kwargs.pop("inject_as")

        # 剩余的 kwargs 全部作为配置项
        self.override_config.update(kwargs)

    def _prepare_kwargs(self, func: Callable, args: tuple, kwargs: dict) -> dict:
        """
        准备注入参数。
        """
        # 1. 尝试从全局配置补全凭据
        final_config = {
            "app_id": getattr(Config, "FEISHU_APP_ID", None),
            "app_secret": getattr(Config, "FEISHU_APP_SECRET", None),
            **DEFAULT_CLIENT_CONFIG,
            **self.override_config,
        }

        # 2. 获取或创建 Client
        client = _get_cached_client(final_config)

        # 3. 智能注入
        sig = inspect.signature(func)
        bound_args = sig.bind_partial(*args, **kwargs)
        if (
            self.inject_as in sig.parameters
            and self.inject_as not in bound_args.arguments
        ):
            kwargs[self.inject_as] = client

        return kwargs

    def __call__(self, func: T) -> T:
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                kwargs = self._prepare_kwargs(func, args, kwargs)
                return await func(*args, **kwargs)

            return async_wrapper  # type: ignore
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                kwargs = self._prepare_kwargs(func, args, kwargs)
                return func(*args, **kwargs)

            return sync_wrapper  # type: ignore
