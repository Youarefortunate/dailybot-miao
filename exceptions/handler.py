import asyncio
import traceback
import functools
from loguru import logger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .base import BusinessException
from .result import Result
from enums.result_code import ResultCode


class GlobalExceptionHandler:
    """
    全局异常处理器，类似于 SpringBoot 的 @ControllerAdvice
    """

    @staticmethod
    def register(app: FastAPI):

        @app.exception_handler(BusinessException)
        async def business_exception_handler(request: Request, exc: BusinessException):
            """捕获 Web 业务异常"""
            logger.warning(f"Web 业务异常: {exc.msg} (Code: {exc.code})")
            return JSONResponse(
                status_code=200, content=Result.fail(code=exc.code, msg=exc.msg).dict()
            )

        @app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            """捕获 Web 全局未处理异常"""
            logger.error(f"Web 系统异常: {str(exc)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content=Result.fail(
                    code=ResultCode.ERROR.code, msg=ResultCode.ERROR.msg
                ).dict(),
            )


def handle_logic_exception(func):
    """
    逻辑异常处理装饰器，用于非 Web 环境（如 main.py）
    支持同步 (def) 和 异步 (async def) 函数
    """

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except BusinessException as e:
            logger.warning(f"💡 逻辑执行警告: {e.msg} (Code: {e.code})")
        except Exception as e:
            logger.error(f"🚨 逻辑执行崩溃: {str(e)}\n{traceback.format_exc()}")

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BusinessException as e:
            logger.warning(f"💡 逻辑执行警告: {e.msg} (Code: {e.code})")
        except Exception as e:
            logger.error(f"🚨 逻辑执行崩溃: {str(e)}\n{traceback.format_exc()}")

    # 自动识别函数类型并返回对应的包装器
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
