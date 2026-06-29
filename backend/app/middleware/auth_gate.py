"""全局 API 鉴权：除登录/健康检查外，/api 需携带 JWT；admin 与工单写操作按角色限制。"""
from __future__ import annotations

from typing import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.config import settings
from app.services import auth_service

PUBLIC_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
)

PUBLIC_EXACT = {
    "/",
    "/health",
}


def _is_public(path: str, method: str) -> bool:
    if path in PUBLIC_EXACT:
        return True
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return True
    prefix = settings.api_prefix.rstrip("/")
    if path == f"{prefix}/auth/login" and method == "POST":
        return True
    if path == f"{prefix}/auth/demo-accounts" and method == "GET":
        return True
    return False


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization") or ""
    parts = auth.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


def _forbidden(msg: str) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": msg})


def _unauthorized(msg: str = "请先登录") -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": msg})


async def auth_gate_middleware(request: Request, call_next: Callable) -> Response:
    if not settings.auth_enabled:
        return await call_next(request)

    path = request.url.path
    method = request.method.upper()

    if _is_public(path, method):
        return await call_next(request)

    prefix = settings.api_prefix.rstrip("/")
    if not path.startswith(f"{prefix}/"):
        return await call_next(request)

    token = _extract_bearer(request)
    if not token:
        return _unauthorized()

    try:
        user = auth_service.decode_token(token)
    except HTTPException:
        return _unauthorized("无效登录凭证")

    request.state.user = user
    role = user.get("role")

    if path.startswith(f"{prefix}/admin"):
        if role != "admin":
            return _forbidden("仅系统管理员可访问管理接口")

    if path.startswith(f"{prefix}/incidents") and method in {"POST", "PATCH", "DELETE"}:
        if role not in {"admin", "ops"}:
            return _forbidden("仅运维工程师或管理员可修改工单")

    if path.startswith(f"{prefix}/v2/") and method == "POST":
        if role not in {"admin", "ops"}:
            return _forbidden("仅运维工程师或管理员可执行现场识别等写操作")

    return await call_next(request)
