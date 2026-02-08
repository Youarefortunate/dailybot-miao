import requests


class HttpRequest:
    """
    HTTP 请求类
    """

    def __init__(self, opts=None):
        if opts is None:
            opts = {}

        self.session = requests.Session()
        self.timeout = opts.get("timeout", 10)
        self.base_url = opts.get("baseURL", "")

        self.before_functions = []
        self.request_interceptor = None
        self.response_interceptor = None

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
        self.session.headers.update({key: value})

    def request(self, config):
        """
        发起请求
        """
        # 执行请求前的钩子函数
        for fn in self.before_functions:
            fn()

        # 执行请求拦截器
        if self.request_interceptor:
            callback, fail = self.request_interceptor
            try:
                config = callback(config) or config
            except Exception as e:
                if fail:
                    fail(e)
                raise e

        # 构造请求参数
        method = config.get("method", "GET").upper()
        url = config.get("url", "")
        if not url.startswith("http") and self.base_url:
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

        params = config.get("params")
        data = config.get("data")
        json_data = config.get("json")
        headers = config.get("headers", {})

        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_data,
                headers=headers,
                timeout=config.get("timeout", self.timeout),
            )

            # 响应拦截器
            if self.response_interceptor:
                callback, fail = self.response_interceptor
                try:
                    # 将 config 传递给拦截器，方便重试
                    return callback(resp, config)
                except Exception as e:
                    if fail:
                        return fail(e, config)
                    raise e
            return resp
        except Exception as e:
            if self.response_interceptor:
                _, fail = self.response_interceptor
                if fail:
                    return fail(e, config)
            raise e

    def get_instance(self):
        """
        返回一个可调用对象
        """
        return self.request
