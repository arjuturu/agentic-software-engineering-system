import logging
from contextvars import ContextVar

correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_context.get() or "-"
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(CorrelationIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "[correlation_id=%(correlation_id)s] %(message)s"
        )
    )
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())
