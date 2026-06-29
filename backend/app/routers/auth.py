from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config import settings
from app.deps.auth import get_current_user
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=3, max_length=64)


@router.post("/login")
def login(body: LoginBody) -> dict[str, Any]:
    user = auth_service.authenticate(body.username, body.password)
    token, expires_in = auth_service.create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user,
    }


@router.get("/me")
def me(current: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"user": current, "auth_enabled": settings.auth_enabled}


@router.get("/demo-accounts")
def demo_accounts() -> dict[str, Any]:
    return {"items": auth_service.demo_accounts_public(), "auth_enabled": settings.auth_enabled}
