"""One error shape for the whole API: {"error": code, "message": text}.

Clients never see stack traces or internals (A02/A10). The full error code table is
product_backend.md §1.1.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Raise from anywhere (controllers, dependencies) to return a clean error response."""

    def __init__(
        self,
        status: int,
        error: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
        **extra,
    ):
        super().__init__(error)
        self.status = status
        self.error = error
        self.message = message
        self.headers = headers
        self.extra = extra  # e.g. attempts_left=2


def error_response(status: int, error: str, message: str, headers=None, **extra) -> JSONResponse:
    return JSONResponse({"error": error, "message": message, **extra}, status, headers=headers)


# Generic messages for errors raised by the framework itself (unknown route, wrong method, ...).
_HTTP_ERRORS = {
    401: ("unauthorized", "Please log in again."),
    404: ("not_found", "Not found."),
    405: ("method_not_allowed", "Method not allowed."),
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError):
        return error_response(exc.status, exc.error, exc.message, exc.headers, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError):
        # Field names only. Pydantic's own messages can echo the submitted value.
        fields = sorted({str(err["loc"][-1]) for err in exc.errors() if err.get("loc")})
        return error_response(422, "validation_error", "Some fields are invalid.", fields=fields)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException):
        error, message = _HTTP_ERRORS.get(exc.status_code, ("error", "Request failed."))
        return error_response(exc.status_code, error, message, getattr(exc, "headers", None))
