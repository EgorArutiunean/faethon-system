import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

import sentry_sdk
from fastapi import FastAPI, Request

from app.core.metrics import request_metrics

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or request_id_context.get()
        if request_id:
            payload["request_id"] = request_id
        for field in ("method", "path", "status_code", "duration_ms", "error_type"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str, *, json_logs: bool) -> None:
    handler = logging.StreamHandler()
    formatter = (
        JsonFormatter() if json_logs else logging.Formatter("%(levelname)s %(name)s %(message)s")
    )
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())
    for logger_name in ("uvicorn", "uvicorn.error"):
        server_logger = logging.getLogger(logger_name)
        server_logger.handlers.clear()
        server_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def _request_id(request: Request) -> str:
    supplied = request.headers.get(REQUEST_ID_HEADER, "")
    return supplied if _REQUEST_ID_PATTERN.fullmatch(supplied) else uuid4().hex


def install_request_logging(app: FastAPI) -> None:
    logger = logging.getLogger("buy_modern.request")

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = _request_id(request)
        token = request_id_context.set(request_id)
        sentry_sdk.set_tag("request_id", request_id)
        started = perf_counter()
        request_metrics.started()
        status_code = 500
        fields: dict[str, object] = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        }
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            fields.update(
                status_code=500,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                error_type=type(exc).__name__,
            )
            logger.error("request_failed", extra=fields)
            raise
        else:
            response.headers[REQUEST_ID_HEADER] = request_id
            fields.update(
                status_code=status_code,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            logger.info("request_completed", extra=fields)
            return response
        finally:
            route = request.scope.get("route")
            route_path = getattr(route, "path", "unmatched")
            request_metrics.finished(
                request.method,
                route_path,
                status_code,
                perf_counter() - started,
            )
            request_id_context.reset(token)
