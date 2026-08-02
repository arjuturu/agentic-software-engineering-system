from fastapi import FastAPI, Request

from app import __version__
from app.api.error_handlers import register_error_handlers
from app.api.router import api_router
from app.config import get_settings
from app.core.identifiers import new_correlation_id
from app.core.logging import configure_logging, correlation_id_context


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    application = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        description="Governed local agentic SDLC automation system",
    )

    @application.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or new_correlation_id()
        request.state.correlation_id = correlation_id
        token = correlation_id_context.set(correlation_id)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            correlation_id_context.reset(token)

    @application.get("/", tags=["system"])
    def root() -> dict[str, str]:
        return {"name": settings.APP_NAME, "version": __version__, "docs": "/docs"}

    application.include_router(api_router)
    register_error_handlers(application)
    return application


app = create_app()
