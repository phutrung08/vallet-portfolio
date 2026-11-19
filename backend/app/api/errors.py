"""Every error leaves the API as ``{"code", "message"}``; the UI maps codes to localized text."""

import logging
from collections.abc import Mapping
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api.security_headers import security_headers_dict
from app.services.errors import RuleCode, RuleViolation

logger = logging.getLogger(__name__)

_CODES_BY_STATUS = {
    HTTPStatus.UNAUTHORIZED: "unauthenticated",
    HTTPStatus.NOT_FOUND: "not_found",
    HTTPStatus.METHOD_NOT_ALLOWED: "method_not_allowed",
    HTTPStatus.CONFLICT: "conflict",
}

_RULE_ERRORS: dict[RuleCode, tuple[HTTPStatus, str]] = {
    "trip_locked": (HTTPStatus.FORBIDDEN, "Trip is locked"),
    "trip_closed": (HTTPStatus.FORBIDDEN, "Trip is closed"),
    "name_taken": (HTTPStatus.CONFLICT, "Name is already taken"),
    "trip_full": (HTTPStatus.CONFLICT, "Trip is full"),
    "trip_limit_reached": (HTTPStatus.CONFLICT, "Trip limit reached"),
    "device_trip_limit_reached": (HTTPStatus.CONFLICT, "Device trip limit reached"),
    "member_is_fund_holder": (HTTPStatus.CONFLICT, "Member holds the fund"),
    "member_already_joined": (
        HTTPStatus.CONFLICT,
        "Member has already joined on another device",
    ),
    "last_member": (HTTPStatus.CONFLICT, "Cannot remove the last member"),
    "member_not_active": (HTTPStatus.CONFLICT, "Member is not active in this trip"),
    "no_fund": (HTTPStatus.CONFLICT, "Trip has no shared fund"),
    "fund_in_use": (HTTPStatus.CONFLICT, "Fund has contributions or fund-paid expenses"),
    "invalid_split": (HTTPStatus.UNPROCESSABLE_ENTITY, "Split does not add up"),
    "currency_not_supported": (HTTPStatus.CONFLICT, "VietQR needs a VND trip"),
    "no_bank_account": (HTTPStatus.CONFLICT, "Member has no bank account"),
    "idempotency_conflict": (HTTPStatus.CONFLICT, "Idempotency key was used for another request"),
    "version_conflict": (HTTPStatus.CONFLICT, "Expense was changed by someone else"),
}


def error_response(
    status: int, code: str, message: str, headers: Mapping[str, str] | None = None, **extra: object
) -> JSONResponse:
    """Create a canonical ``{"code", "message"}`` JSON error response."""
    return JSONResponse({"code": code, "message": message, **extra}, status, headers)


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise TypeError(f"Expected HTTPException, got {type(exc).__name__}")
    status = HTTPStatus(exc.status_code)
    # The status phrase, never exc.detail, so no handler can leak internals into the body.
    code = _CODES_BY_STATUS.get(status, "http_error")
    return error_response(status, code, status.phrase, exc.headers)


async def handle_rule_violation(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RuleViolation):
        raise TypeError(f"Expected RuleViolation, got {type(exc).__name__}")
    status, message = _RULE_ERRORS[exc.code]
    extra: dict[str, object] = {} if exc.difference is None else {"difference": exc.difference}
    return error_response(status, exc.code, message, None, **extra)


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise TypeError(f"Expected RequestValidationError, got {type(exc).__name__}")
    # Field paths only: pydantic's "input" and "ctx" would echo what the client sent.
    fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
    return error_response(422, "validation_error", "Invalid request", fields=fields)


def register_error_handlers(app: FastAPI, *, hsts: bool = True) -> None:
    """Register exception handlers, including security headers on Starlette-handled HTTP 500."""
    fallback_headers = security_headers_dict(hsts=hsts)

    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Method and path only: bodies, query strings and cookies may hold secrets.
        logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return error_response(
            500, "internal_error", "Internal server error", headers=fallback_headers
        )

    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RuleViolation, handle_rule_violation)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
