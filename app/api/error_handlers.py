import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.exceptions import ApplicationError
from app.core.identifiers import new_correlation_id
from app.core.time import utc_now

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    errorCode: str
    message: str
    correlationId: str
    timestamp: str


def _error_payload(error_code: str, message: str, correlation_id: str) -> dict[str, str]:
    return ErrorResponse(
        errorCode=error_code,
        message=message,
        correlationId=correlation_id,
        timestamp=utc_now().isoformat(),
    ).model_dump()


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request, exception: ApplicationError
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", new_correlation_id())
        return JSONResponse(
            status_code=exception.status_code,
            content=_error_payload(exception.error_code, exception.message, correlation_id),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exception: RequestValidationError
    ) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", new_correlation_id())
        logger.info("Request validation failed: %s", exception.errors())
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "VALIDATION_ERROR", "The request contains invalid data.", correlation_id
            ),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exception: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", new_correlation_id())
        logger.exception("Unexpected application error", exc_info=exception)
        return JSONResponse(
            status_code=500,
            content=_error_payload(
                "INTERNAL_ERROR", "An unexpected error occurred.", correlation_id
            ),
        )
