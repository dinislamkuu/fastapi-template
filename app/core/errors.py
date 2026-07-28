from __future__ import annotations

from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_id import REQUEST_ID_HEADER, get_request_id
from app.schemas.errors import ErrorBody, ErrorResponse

logger = structlog.get_logger(__name__)


def _request_id_from(request: Request) -> str | None:
    state_request_id = getattr(request.state, "request_id", None)
    return state_request_id if isinstance(state_request_id, str) else get_request_id()


def _error_response(request: Request, *, code: str, message: str, status_code: int) -> JSONResponse:
    request_id = _request_id_from(request)
    payload = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id)
    ).model_dump()
    headers = {REQUEST_ID_HEADER: request_id} if request_id is not None else None
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return _error_response(
            request,
            code="internal_server_error",
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    return _error_response(request, code="http_error", message=message, status_code=exc.status_code)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return _error_response(
            request,
            code="internal_server_error",
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return _error_response(
        request,
        code="validation_error",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        exc_info=exc,
    )
    return _error_response(
        request,
        code="internal_server_error",
        message="Internal server error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
