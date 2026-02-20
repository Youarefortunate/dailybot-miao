import httpx
import asyncio


class HttpRequest:
    """
    HTTP 请求类 (基于 httpx 实现异步支持)
    """

    # 类级别的异步客户端，实现全局连接池复用
    _client: httpx.AsyncClient = None
    _lock = asyncio.Lock()

    def __init__(self, opts=None):
        if opts is None:
            opts = {}

        self.base_url = opts.get("baseURL", "")
        self.headers = {}  # 实例私有 Header，避免共享 Client 污染
        self.timeout = opts.get("timeout", 60.0)

        self.before_functions = []
        self.request_interceptor = None
        self.response_interceptor = None

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        """
        获取或初始化全局共享的异步客户端
        """
        if cls._client is None:
            async with cls._lock:
                if cls._client is None:
                    cls._client = httpx.AsyncClient(
                        timeout=httpx.Timeout(60.0, connect=5.0),
                        follow_redirects=True,
                    )
        return cls._client

    @classmethod
    async def close_all(cls):
        """
        关闭全局共享客户端 (通常在程序退出时调用)
        """
        if cls._client:
            await cls._client.aclose()
            cls._client = None

    def before_request(self, fn):
        if callable(fn):
            self.before_functions.append(fn)

    def set_req_interceptors(self, callback, fail=None):
        self.request_interceptor = (callback, fail)

    def set_res_interceptors(self, callback, fail=None):
        self.response_interceptor = (callback, fail)

    def set_base_url(self, url):
        self.base_url = url

    def set_headers(self, key, value):
        self.headers.update({key: value})

    async def request(self, config):
        """
        发起异步请求
        """
        # 执行请求前的钩子函数 (目前保持同步)
        for fn in self.before_functions:
            fn()

        # 执行请求拦截器 (支持同步和异步)
        if self.request_interceptor:
            callback, fail = self.request_interceptor
            try:
                if asyncio.iscoroutinefunction(callback):
                    config = (await callback(config)) or config
                else:
                    res = callback(config)
                    if asyncio.iscoroutine(res):
                        config = (await res) or config
                    else:
                        config = res or config
            except Exception as e:
                if fail:
                    if asyncio.iscoroutinefunction(fail):
                        await fail(e)
                    else:
                        fail(e)
                raise e

        # 构造请求参数
        method = config.get("method", "GET").upper()
        url = config.get("url", "")
        if not url.startswith("http") and self.base_url:
            url = (
                f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
                if url
                else self.base_url
            )

        params = config.get("params")
        data = config.get("data")
        json_data = config.get("json")
        headers = config.get("headers", {})
        timeout = config.get("timeout")

        try:
            # 获取共享客户端
            client = await self.get_client()

            # 合并 Headers: 共享 Client (默认) <- 实例私有 (self.headers) <- 请求临时 (headers)
            final_headers = client.headers.copy()
            final_headers.update(self.headers)
            final_headers.update(headers)

            # 调用 httpx 的异步请求方法
            resp = await client.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_data,
                headers=final_headers,
                timeout=timeout if timeout is not None else self.timeout,
            )

            # 响应拦截器
            if self.response_interceptor:
                callback, fail = self.response_interceptor
                try:
                    # 将 config 传递给拦截器，方便重试
                    # 注意：如果拦截器内部需要重新发起请求，它也必须是异步的
                    if asyncio.iscoroutinefunction(callback):
                        return await callback(resp, config)
                    else:
                        return callback(resp, config)
                except Exception as e:
                    if fail:
                        if asyncio.iscoroutinefunction(fail):
                            return await fail(e, config)
                        else:
                            return fail(e, config)
                    raise e
            return resp
        except Exception as e:
            if self.response_interceptor:
                _, fail = self.response_interceptor
                if fail:
                    if asyncio.iscoroutinefunction(fail):
                        return await fail(e, config)
                    else:
                        return fail(e, config)
            raise e

    def get_instance(self):
        """
        返回一个可调用对象
        """
        return self.request
