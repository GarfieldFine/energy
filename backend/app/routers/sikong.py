from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.services import sikong_qa

router = APIRouter(prefix="/sikong", tags=["sikong-dataset"])


@router.get("/status")
def sikong_status() -> dict[str, Any]:
    return {
        "ready": sikong_qa.is_ready(),
        "rows": sikong_qa.count_rows(),
        "jsonl_path": str(settings.sikong_jsonl),
    }


@router.get("/search")
def sikong_search(
    q: str = Query(..., min_length=1, description="关键词，空格分隔多词"),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    return sikong_qa.search_sikong(q, limit=limit)


class RagBody(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20)


@router.post("/rag-demo")
def sikong_rag(body: RagBody) -> dict[str, Any]:
    return sikong_qa.rag_sikong_demo(body.query, limit=body.top_k)
