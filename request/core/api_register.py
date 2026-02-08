import time
import random
import re
from .dot_dict import DotDict
from .http_request import HttpRequest
from ..platforms.modules.platform_manager import platform_manager


class ApiRegister:
    """
    API 注册类
    """

    def __init__(self):
        self.apis = DotDict()
        self._api_configs = {}
        self._hooks = []
        self._platform_instances = {}  # 缓存不同平台的请求实例
        self.request = None
        self.platform = None

    def set_request(self, request):
        self.request = request

    def set_platform(self, platform):
        self.platform = platform

    def use(self, callback):
        if callable(callback):
            self._hooks.append(callback)

    def _get_platform_request(self, platform_name, url=None):
        """
        根据URL或平台名称获取或创建对应的请求实例
        """
        detected_platform = platform_name
        if url:
            detected = platform_manager.detect_platform(url)
            if detected:
                detected_platform = detected

        if detected_platform in self._platform_instances:
            return self._platform_instances[detected_platform]

        # 创建新的请求实例
        http_request = HttpRequest()

        # 创建平台实例并配置请求
        platform_instance = platform_manager.create_platform(detected_platform)
        if platform_instance:
            platform_instance.setup_request(http_request)
            instance = http_request.get_instance()
            self._platform_instances[detected_platform] = instance
            return instance

        return self.request

    def register(self, props, opts=None):
        if opts is None:
            opts = {}
        if isinstance(props, list):
            for v in props:
                self._register_proxy(v, opts)
        else:
            self._register_proxy(props, opts)

    def _register_proxy(self, props, opts):
        if not isinstance(props, dict) or "name" not in props:
            raise ValueError("Registration API model must provide a name attribute")

        name = props["name"]
        rest = {k: v for k, v in props.items() if k != "name"}

        if name not in self._api_configs:
            self._api_configs[name] = {}

        for k, v in rest.items():
            self._api_configs[name][k] = v

        self._register_api_by_name(name, opts)

    def _parse_args(self, str_val):
        parts = str_val.strip().split()
        method, url, platform = "GET", "", None

        if len(parts) >= 3:
            platform, method, *url_parts = parts
            url = " ".join(url_parts)
        elif len(parts) == 2:
            method, url = parts
        elif len(parts) == 1:
            url = parts[0]
            method = "GET"

        return {"method": method, "url": url, "platform": platform}

    def _register_api_by_name(self, name, opts):
        api_methods = self._api_configs[name]
        cache_api = DotDict()
        module_platform = api_methods.get("platform")

        for key, value in api_methods.items():
            if key == "platform":
                continue
            cache_api[key] = self._make_api_callable(name, key, value, module_platform)

        self.apis[name] = cache_api

    def _make_api_callable(self, namespace, key, value, module_platform):
        """
        构造最终可调用的 API 方法
        """
        # 1. 确定配置生成函数及其关联平台
        config_fn, current_platform = self._get_config_builder(value, module_platform)

        # 2. 构造最终的包装函数
        def api_method(payload=None):
            if payload is None:
                payload = {}

            # 解析配置
            data = config_fn(payload) if callable(config_fn) else data

            # 执行钩子 (Hook 系统允许外部拦截请求参数)
            for hook in self._hooks:
                hook(data)

            if isinstance(data, dict):
                # 优先级: 接口返回的 platform > 模块定义的 platform > 全局默认平台
                req_platform = data.get("platform") or current_platform or self.platform or "feishu"
                req_url = data.get("url") or data.get("baseURL")

                # 获取对应平台的请求实例并发起请求
                platform_request = self._get_platform_request(req_platform, req_url)
                return platform_request(data)
            return data

        # 3. 注入唯一的 ID 标识，方便日志追踪
        random_id = random.randint(1000, 9999)
        api_method.id = f"{namespace}_{key}_{int(time.time() * 1000)}_{random_id}"
        return api_method

    def _get_config_builder(self, value, module_platform):
        """
        根据定义格式（字符串、字典、函数）返回配置生成器和预测平台
        """
        current_platform = module_platform

        # 情况 A: 字符串定义 (如 "Github GET /api/user")
        if isinstance(value, str):
            parsed = self._parse_args(value)
            if parsed["platform"]:
                current_platform = parsed["platform"]

            method = parsed["method"].upper()
            raw_url = parsed["url"]

            def string_config_builder(p):
                url = raw_url
                p_remain = p.copy() if isinstance(p, dict) else p

                # 路径参数处理: 将 {id} 替换为 p['id'] 并从 p 中移除
                if isinstance(p_remain, dict):
                    keys = re.findall(r"\{([\w\-]+)\}", url)
                    for k in keys:
                        if k in p_remain:
                            url = url.replace(f"{{{k}}}", str(p_remain.pop(k)))

                res = {"method": method, "url": url}

                # 从参数中分离出 headers/timeout 等控制字段
                if isinstance(p_remain, dict):
                    if "headers" in p_remain:
                        res["headers"] = p_remain.pop("headers")
                    if "timeout" in p_remain:
                        res["timeout"] = p_remain.pop("timeout")

                res[("params" if method == "GET" else "json")] = p_remain
                return res

            return string_config_builder, current_platform

        # 情况 B: 字典定义 (直接返回)
        elif isinstance(value, dict):
            return lambda p: value, current_platform

        # 情况 C: 函数定义 (如 login(params))
        elif callable(value):
            # 直接透传用户定义的函数
            return value, current_platform

        return lambda p: {}, current_platform

    def define(self, name, api_methods=None):
        if api_methods is None:
            api_methods = {}

        methods = api_methods() if callable(api_methods) else api_methods
        self._register_proxy({"name": name, **methods}, {})
