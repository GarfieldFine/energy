from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.services import kb_search

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


@router.get("/status")
def kb_status() -> dict[str, Any]:
    return {
        "index_ready": kb_search.is_index_ready(),
        "index_path": str(settings.kb_index_db),
    }


@router.get("/search")
def kb_search_get(
    q: str = Query(..., min_length=1),
    limit: int = Query(15, ge=1, le=50),
) -> dict[str, Any]:
    return kb_search.search_kb(q, limit=limit)


class ChatBody(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20)


@router.post("/rag-demo")
def rag_demo(body: ChatBody) -> dict[str, Any]:
    """演示：检索 + 模板拼接（接入真实 LLM 时可替换此路由）。"""
    return kb_search.rag_stub_answer(body.query, limit=body.top_k)
