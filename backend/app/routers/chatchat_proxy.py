"""
将智能问答请求转发到队友机器上的 Langchain-Chatchat HTTP API（避免浏览器跨域）。
需在 backend/.env 配置 CHATCHAT_BASE_URL，例如 http://192.168.1.10:7861
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter(prefix="/chatchat", tags=["chatchat-proxy"])


@router.get("/status")
async def chatchat_status() -> dict[str, Any]:
    """是否已配置上游地址，以及能否访问其 /docs（粗略探测）。"""
    base = settings.chatchat_base_url
    if not base:
        return {
            "configured": False,
            "reachable": None,
            "base_url": None,
            "hint": "在 backend/.env 中设置 CHATCHAT_BASE_URL（队友 Chatchat API 根地址，无末尾斜杠）",
        }
    url = base.rstrip("/") + "/docs"
    try:
        async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
            r = await client.get(url, follow_redirects=True)
        return {
            "configured": True,
            "reachable": r.status_code < 500,
            "base_url": base,
            "upstream_status": r.status_code,
        }
    except httpx.RequestError as e:
        return {
            "configured": True,
            "reachable": False,
            "base_url": base,
            "error": str(e),
        }


@router.post("/kb-chat")
async def chatchat_kb_chat_proxy(payload: dict[str, Any] = Body(...)) -> Any:
    """
    转发到 Chatchat `POST /chat/kb_chat`（知识库对话）。
    请求体字段与上游一致，常用：query, kb_name, mode=local_kb, stream=false
    """
    base = settings.chatchat_base_url
    if not base:
        raise HTTPException(
            status_code=503,
            detail="未配置 CHATCHAT_BASE_URL，无法转发到 Langchain-Chatchat",
        )
    q = payload.get("query")
    if not (isinstance(q, str) and q.strip()):
        raise HTTPException(status_code=422, detail="query 不能为空")

    merged: dict[str, Any] = {**payload}
    merged.setdefault("stream", False)

    url = base.rstrip("/") + "/chat/kb_chat"
    timeout = httpx.Timeout(settings.chatchat_timeout_sec)
    try:
        # trust_env=False：避免本机 HTTP(S)_PROXY 把内网 10.x 请求拐到错误代理
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            r = await client.post(url, json=merged)
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=502,
            detail=(
                f"无法连接到 Chatchat（连接被拒绝或网络不可达）: {e}。"
                "请确认队友机器 Chatchat 已启动、防火墙放行 7861、Docker 端口映射为 0.0.0.0:7861，"
                "且校园网未做终端隔离。"
            ),
        ) from e
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=502,
            detail=f"连接 Chatchat 超时: {e}。可适当增大 CHATCHAT_TIMEOUT_SEC 或检查网络。",
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"无法连接 Chatchat 服务: {e}") from e

    ct = (r.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        try:
            data = r.json()
        except json.JSONDecodeError:
            data = {"raw_text": r.text[:8000]}
        return JSONResponse(content=data, status_code=r.status_code)

    # 少数情况下上游返回纯文本 JSON 串
    text = r.text.strip()
    if text.startswith("{") or text.startswith("["):
        try:
            return JSONResponse(content=json.loads(text), status_code=r.status_code)
        except json.JSONDecodeError:
            pass
    return JSONResponse(
        status_code=r.status_code,
        content={"detail": "非 JSON 响应", "text": text[:8000]},
    )
