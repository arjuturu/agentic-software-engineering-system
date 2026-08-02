from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy.orm import Session, sessionmaker

from app import __version__
from app.api.error_handlers import register_error_handlers
from app.api.router import api_router
from app.config import Settings, get_settings
from app.core.identifiers import new_correlation_id
from app.core.logging import configure_logging, correlation_id_context
from app.database.session import create_database_engine, get_db
from app.services.workflow_service import WorkflowService, create_workflow_runtime


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(active_settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(active_settings.DATABASE_URL)
        sessions = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
        runtime = create_workflow_runtime(active_settings, sessions)
        application.state.workflow_runtime = runtime
        application.state.workflow_service = WorkflowService(runtime)

        def database_dependency() -> Iterator[Session]:
            with sessions() as session:
                yield session

        if get_db not in application.dependency_overrides:
            application.dependency_overrides[get_db] = database_dependency
        try:
            yield
        finally:
            runtime.close()
            engine.dispose()

    application = FastAPI(
        title=active_settings.APP_NAME,
        version=__version__,
        description="Governed local agentic SDLC automation system",
        lifespan=lifespan,
    )
    if settings is not None:
        application.dependency_overrides[get_settings] = lambda: active_settings

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
        return {"name": active_settings.APP_NAME, "version": __version__, "docs": "/docs"}

    application.include_router(api_router)
    register_error_handlers(application)
    return application


app = create_app()
