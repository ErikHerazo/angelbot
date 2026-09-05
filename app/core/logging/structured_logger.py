"""Structured, tagged logging for the hexagonal codebase.

Tags (an "event type" dimension, separate from severity level):
  INIT    - a function/method started (input params as fields)
  END     - it finished successfully (result summary + duration_ms)
  ERROR   - it raised (exception type/message + duration_ms if inside `operation`)
  WARNING - something degraded but was recovered from (e.g. a fallback kicked in)
  INFO    - a noteworthy internal event that's neither start nor end
  DEBUG   - fine-grained flow detail (intermediate values, which branch was taken)

Every call auto-detects the caller's function/method name (no need to pass
it manually -- one less thing to get stale after a refactor) and attaches
structured fields via `extra`, namespaced under `structured_fields` so they
never collide with reserved `LogRecord` attributes.

Console output is human-readable today. Set `LOG_FORMAT=json` to switch to
one JSON object per line (e.g. once there's a real log aggregator to ship
to) with zero call-site changes -- only the formatter changes.

Usage:
    from app.core.logging.structured_logger import get_logger

    log = get_logger(__name__)

    class ProcessIncomingMessage:
        async def execute(self, *, tenant_id, request_id, ...):
            with log.operation(tenant_id=tenant_id, request_id=request_id):
                ...  # INIT logged on entry, END (with duration_ms) on
                     # success, ERROR (with duration_ms + exception) if it
                     # raises -- the exception is re-raised, never swallowed.

    log.info("cache hit", tenant_id=tenant_id)
    log.warning("Redis read failed, continuing without history", session_id=session_id)
"""

import contextlib
import json
import logging
import os
import sys
import time
from typing import Any, Iterator

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_FORMAT = os.getenv("LOG_FORMAT", "console").lower()  # "console" | "json"


class _StructuredConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        fields = getattr(record, "structured_fields", None) or {}
        if not fields:
            return base
        fields_str = " ".join(f"{k}={v!r}" for k, v in fields.items())
        return f"{base} | {fields_str}"


class _StructuredJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "tag": getattr(record, "tag", None),
            "logger": record.name,
            "function": getattr(record, "func_name", None),
            "message": record.getMessage(),
            **(getattr(record, "structured_fields", None) or {}),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def _build_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    if _LOG_FORMAT == "json":
        handler.setFormatter(_StructuredJSONFormatter())
    else:
        handler.setFormatter(
            _StructuredConsoleFormatter(
                "%(asctime)s %(levelname)s [%(tag)s] %(func_name)s: %(message)s",
                "%Y-%m-%d %H:%M:%S",
            )
        )
    return handler


def _caller_qualname(depth: int) -> str:
    frame = sys._getframe(depth)
    func_name = frame.f_code.co_name

    self_obj = frame.f_locals.get("self")
    if self_obj is not None:
        return f"{type(self_obj).__name__}.{func_name}"

    cls_obj = frame.f_locals.get("cls")
    if cls_obj is not None:
        return f"{cls_obj.__name__}.{func_name}"

    return func_name


class StructuredLogger:
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _emit(
        self,
        tag: str,
        level: int,
        func_name: str,
        message: str,
        fields: dict,
        exc_info: bool = False,
    ) -> None:
        self._logger.log(
            level,
            message,
            extra={"tag": tag, "func_name": func_name, "structured_fields": fields},
            exc_info=exc_info,
        )

    def info(self, message: str, **fields: Any) -> None:
        self._emit("INFO", logging.INFO, _caller_qualname(2), message, fields)

    def debug(self, message: str, **fields: Any) -> None:
        self._emit("DEBUG", logging.DEBUG, _caller_qualname(2), message, fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._emit("WARNING", logging.WARNING, _caller_qualname(2), message, fields)

    def error(self, message: str, *, exc_info: bool = True, **fields: Any) -> None:
        self._emit("ERROR", logging.ERROR, _caller_qualname(2), message, fields, exc_info=exc_info)

    @contextlib.contextmanager
    def operation(self, **fields: Any) -> Iterator[None]:
        """Logs INIT on entry, END (with duration_ms) on success, ERROR
        (with duration_ms + exception info) if the body raises -- the
        exception always propagates, never swallowed here."""
        func_name = _caller_qualname(3)
        start = time.monotonic()
        self._emit("INIT", logging.INFO, func_name, "start", dict(fields))

        try:
            yield
        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            self._emit(
                "ERROR",
                logging.ERROR,
                func_name,
                str(exc),
                {**fields, "duration_ms": duration_ms, "error_type": type(exc).__name__},
                exc_info=True,
            )
            raise
        else:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            self._emit("END", logging.INFO, func_name, "end", {**fields, "duration_ms": duration_ms})


_configured_logger_names: set[str] = set()


def get_logger(name: str) -> StructuredLogger:
    logger = logging.getLogger(name)

    if name not in _configured_logger_names:
        logger.setLevel(_LOG_LEVEL)
        logger.propagate = False
        logger.addHandler(_build_handler())
        _configured_logger_names.add(name)

    return StructuredLogger(logger)
