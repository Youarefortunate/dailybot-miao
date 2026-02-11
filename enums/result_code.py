from enum import Enum


class ResultCode(Enum):
    """
    业务响应状态码枚举
    """

    SUCCESS = (200, "操作成功")
    ERROR = (500, "系统繁忙，请稍后再试")
    PARAM_ERROR = (400, "参数错误")
    AUTH_ERROR = (401, "认证失败")
    BIZ_ERROR = (400, "业务异常")

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg

    @property
    def get_code(self):
        return self.code

    @property
    def get_msg(self):
        return self.msg
