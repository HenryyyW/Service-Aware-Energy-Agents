"""Structured logging configuration with JSON output and correlation IDs."""
import logging
import sys
import uuid
from typing import Any, Dict
from contextvars import ContextVar
from pythonjsonlogger import jsonlogger

# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get() or "-"
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["correlation_id"] = getattr(record, "correlation_id", "-")


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure application logging."""
    log_level = getattr(logging, log_level.upper(), logging.INFO)

    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if log_format == "json":
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(correlation_id)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S.%fZ",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    console_handler.addFilter(CorrelationIdFilter())
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str = None) -> str:
    """Set correlation ID for current context."""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())[:8]
    correlation_id_var.set(correlation_id)
    return correlation_id


def clear_correlation_id() -> None:
    """Clear correlation ID."""
    correlation_id_var.set("")