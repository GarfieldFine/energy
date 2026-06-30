"""HTTP 请求访问日志（POC：stdout，不含请求体）。"""
from __future__ import annotations

import logging
import time

from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.access")

_SKIP_PREFIXES = ("/docs", "/openapi.json", "/redoc")


async def request_log_middleware(request: Request, call_next) -> Response:
    path = request.url.path
    if path.startswith(_SKIP_PREFIXES):
        return await call_next(request)

    started = time.perf_counter()
    client = request.client.host if request.client else "-"
    method = request.method
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.exception("%s %s %s -> error %.1fms", client, method, path, elapsed_ms)
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("%s %s %s -> %s %.1fms", client, method, path, response.status_code, elapsed_ms)
    return response
