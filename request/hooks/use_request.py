from ..core.dot_dict import DotDict


class RequestState:
    """
    请求状态类
    """

    def __init__(self, loading=False):
        self.data = None
        self.error = None
        self.loading = loading
        self.code = None
        self.message = ""


def use_request(api, config=None):
    """
    普通非分页请求 hook
    """
    if not api:
        raise ValueError("API不存在")

    if config is None:
        config = {}

    state = RequestState(loading=config.get("loading", False))

    def fetch(*args, **kwargs):
        state.loading = True
        try:
            if not callable(api):
                raise ValueError("api 不是函数")

            # 响应结果
            result = api(*args, **kwargs)

            # 获取平台定义的响应模板，如果没有则使用默认模板
            template = getattr(result, "response_template", {"code": "code", "data": "data", "message": "message"})

            code_key = template.get("code", "code")
            data_key = template.get("data", "data")
            msg_key = template.get("message", "message")

            if hasattr(result, "json"):
                try:
                    res_json = result.json()
                    state.code = res_json.get(code_key)
                    state.message = res_json.get(msg_key, "")

                    # 判断业务逻辑是否成功 (兼容 0, 200 或未返回 code 的情况)
                    is_success = state.code in [0, 200, None]

                    if res_json.get(data_key) is not None:
                        state.data = res_json.get(data_key)
                        state.error = None
                    elif is_success:
                        # 如果业务成功但没有指定的数据包裹层，则返回整个 JSON
                        state.data = res_json
                        state.error = None
                    else:
                        state.error = state.message
                        # 如果没有数据且有错误信息，则视为失败
                        if state.message:
                            raise Exception(state.message)
                except Exception as json_err:
                    # 兼容非标准 JSON 或解析失败的情况
                    if not hasattr(result, "json"):
                        state.data = result
                    else:
                        state.data = result.text
                    state.error = str(json_err)
            else:
                state.data = result
                state.error = None

            return state.data
        except Exception as e:
            state.error = str(e) or "Unexpected Error!"
            raise e
        finally:
            state.loading = False

    # 返回一个包含状态和 fetch 方法的 DotDict
    return DotDict({"state": state, "fetch": fetch, "api": api})
