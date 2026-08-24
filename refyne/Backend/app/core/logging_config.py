"""
Structured Logging Configuration.

Sets up JSON-formatted structured logging with trace_id support.
Every log statement across the codebase can include trace_id, user_id, project_id
for full request reconstruction.
"""
import json
import logging
import os
import sys
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for machine-parseable structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include structured fields if present
        for field in ("trace_id", "user_id", "project_id", "event", "duration_ms",
                       "document_id", "chunk_id", "model", "status"):
            val = getattr(record, field, None)
            if val is not None:
                log_entry[field] = val

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable format for development (non-JSON)."""

    def format(self, record: logging.LogRecord) -> str:
        parts = [
            f"{datetime.now(UTC).strftime('%H:%M:%S')}",
            f"[{record.levelname:8s}]",
            f"{record.name}:",
            record.getMessage(),
        ]

        # Append trace_id if present
        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            parts.append(f"[trace={trace_id[:8]}]")

        return " ".join(parts)


def setup_logging(
    level: str | None = None,
    json_format: bool | None = None,
) -> None:
    """
    Configure application-wide structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to LOG_LEVEL env var or INFO.
        json_format: Use JSON formatting. Defaults to LOG_FORMAT=json in production, human in dev.
    """
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")

    if json_format is None:
        json_format = os.environ.get("LOG_FORMAT", "json").lower() == "json"

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(HumanReadableFormatter())

    root_logger.addHandler(handler)

    # Suppress noisy libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance. Convenience wrapper around logging.getLogger."""
    return logging.getLogger(name)
