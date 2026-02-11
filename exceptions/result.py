import time
from typing import Any, Optional
from pydantic import BaseModel
from enums.result_code import ResultCode


class Result(BaseModel):
    """
    统一响应体结构
    """

    code: int
    msg: str
    data: Optional[Any] = None
    timestamp: int = int(time.time() * 1000)

    @staticmethod
    def success(data: Any = None, msg: str = "success"):
        return Result(code=ResultCode.SUCCESS.code, msg=msg, data=data)

    @staticmethod
    def fail(code: int = ResultCode.ERROR.code, msg: str = "fail", data: Any = None):
        return Result(code=code, msg=msg, data=data)

    @staticmethod
    def fail_with_code(result_code: ResultCode, data: Any = None):
        return Result(code=result_code.code, msg=result_code.msg, data=data)

    def is_success(self) -> bool:
        return self.code == ResultCode.SUCCESS.code
