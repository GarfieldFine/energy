from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.services import auth_service

_bearer = HTTPBearer(auto_error=False)

_GUEST: dict[str, Any] = {
    "username": "guest",
    "role": "admin",
    "display_name": "访客（鉴权已关闭）",
    "role_label": "系统管理员",
}


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if not settings.auth_enabled:
        return dict(_GUEST)
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    return auth_service.decode_token(creds.credentials)


def require_roles(*roles: str):
    def _dep(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not settings.auth_enabled:
            return user
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前角色无权执行此操作")
        return user

    return _dep
