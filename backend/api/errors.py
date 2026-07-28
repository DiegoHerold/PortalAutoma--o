from __future__ import annotations

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response


ERROR_CODE_BY_STATUS = {
    status.HTTP_400_BAD_REQUEST: "VALIDATION_ERROR",
    status.HTTP_401_UNAUTHORIZED: "AUTHENTICATION_REQUIRED",
    status.HTTP_403_FORBIDDEN: "PERMISSION_DENIED",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
    status.HTTP_503_SERVICE_UNAVAILABLE: "DEPENDENCY_UNAVAILABLE",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        correlation_id = request.headers.get("x-correlation-id") or f"corr_{uuid4().hex}"
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        payload = error_payload(
            request,
            status_code=exc.status_code,
            message=_detail_message(exc.detail, exc.status_code),
            details=_detail_details(exc.detail),
            code=_detail_code(exc.detail, exc.status_code),
        )
        return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_payload(
                request,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="VALIDATION_ERROR",
                message="Request validation failed.",
                details={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_payload(
                request,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="INTERNAL_ERROR",
                message="Internal server error.",
                details={},
            ),
        )


def http_error(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message, "details": details or {}}})


def error_payload(request: Request, *, status_code: int, message: str, code: str | None = None, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code or ERROR_CODE_BY_STATUS.get(status_code, "INTERNAL_ERROR"),
            "message": message,
            "details": details or {},
            "correlation_id": getattr(request.state, "correlation_id", None),
        }
    }


def _detail_message(detail: object, status_code: int) -> str:
    if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
        message = detail["error"].get("message")
        if message:
            return str(message)
    if isinstance(detail, str) and detail:
        return detail
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Request failed."


def _detail_code(detail: object, status_code: int) -> str:
    if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
        code = detail["error"].get("code")
        if code:
            return str(code)
    return ERROR_CODE_BY_STATUS.get(status_code, "INTERNAL_ERROR")


def _detail_details(detail: object) -> dict:
    if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
        value = detail["error"].get("details")
        return value if isinstance(value, dict) else {}
    if isinstance(detail, dict):
        return detail
    return {}

