from enums.result_code import ResultCode


class BusinessException(Exception):
    """
    业务异常类
    """

    def __init__(self, code: int = ResultCode.BIZ_ERROR.code, msg: str = None):
        self.code = code
        self.msg = msg or ResultCode.BIZ_ERROR.msg
        super().__init__(self.msg)

    @classmethod
    def from_code(cls, result_code: ResultCode):
        return cls(code=result_code.code, msg=result_code.msg)
