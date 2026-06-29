"""轻量 JWT 登录与演示用户管理。"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status

from app.config import settings
from app.services import users_store

ROLE_LABELS: dict[str, str] = {
    "admin": "系统管理员",
    "energy": "能源管理员",
    "ops": "运维工程师",
    "requester": "报修员",
}


def _user_password(username: str, default: str) -> str:
    key = f"AUTH_{username.upper()}_PASSWORD"
    return os.environ.get(key, default).strip() or default


def builtin_users_seed() -> dict[str, dict[str, str]]:
    """演示账号：每位维修师傅对应一个 ops 登录账号（与 technicians 表 username 一致）。"""
    return {
        "admin": {
            "password": _user_password("admin", "admin123"),
            "role": "admin",
            "display_name": "系统管理员",
        },
        "energy": {
            "password": _user_password("energy", "energy123"),
            "role": "energy",
            "display_name": "能源管理员",
        },
        "tech1": {
            "password": _user_password("tech1", "123456"),
            "role": "ops",
            "display_name": "张师傅",
        },
        "tech2": {
            "password": _user_password("tech2", "123456"),
            "role": "ops",
            "display_name": "李师傅",
        },
        "tech3": {
            "password": _user_password("tech3", "123456"),
            "role": "ops",
            "display_name": "王师傅",
        },
        "req1": {
            "password": _user_password("req1", "123456"),
            "role": "requester",
            "display_name": "报修员A",
        },
    }


def authenticate(username: str, password: str) -> dict[str, Any]:
    user = users_store.authenticate((username or "").strip(), password or "")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return user


def create_access_token(user: dict[str, Any]) -> tuple[str, int]:
    expires_sec = int(settings.auth_token_hours * 3600)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["username"],
        "role": user["role"],
        "display_name": user.get("display_name"),
        "role_label": user.get("role_label"),
        "iat": now,
        "exp": now + timedelta(seconds=expires_sec),
    }
    token = jwt.encode(payload, settings.auth_secret, algorithm="HS256")
    return token, expires_sec


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效登录凭证") from e

    username = payload.get("sub")
    role = payload.get("role")
    if not username or role not in ROLE_LABELS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效登录凭证")
    return {
        "username": username,
        "role": role,
        "display_name": payload.get("display_name") or ROLE_LABELS.get(role, role),
        "role_label": payload.get("role_label") or ROLE_LABELS.get(role, role),
    }


def demo_accounts_public() -> list[dict[str, str]]:
    """登录页展示用（不含密码）。"""
    return [
        {
            "username": u["username"],
            "role": u["emsRole"],
            "role_label": ROLE_LABELS.get(u["emsRole"], u["emsRole"]),
            "hint": "演示账号，详见 START.txt",
        }
        for u in users_store.list_users()
    ]
