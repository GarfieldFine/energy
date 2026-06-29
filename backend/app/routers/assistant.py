from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.services import baidu_asr, kb_search, rag_answer, sikong_qa

router = APIRouter(prefix="/assistant", tags=["assistant"])


class UnifiedBody(BaseModel):
    query: str = Field(..., min_length=1)
    kb_pdf_limit: int = Field(8, ge=1, le=30)
    sikong_limit: int = Field(5, ge=1, le=20)


@router.post("/knowledge-merge")
def knowledge_merge(body: UnifiedBody) -> dict[str, Any]:
    """
    赛题智慧运维：合并「规范 PDF 知识库」+「司空 text2text 语料」检索结果，
    供 RAG / 大模型拼装上下文（演示）。
    """
    pdf = kb_search.search_kb(body.query, limit=body.kb_pdf_limit)
    sik = sikong_qa.search_sikong(body.query, limit=body.sikong_limit)
    return {
        "query": body.query,
        "sources": {
            "pdf_kb": {
                "ready": pdf.get("ready"),
                "count": pdf.get("count", 0),
                "items": pdf.get("results", []),
            },
            "sikong_qa": {
                "ready": sik.get("ready"),
                "count": sik.get("count", 0),
                "items": sik.get("results", []),
            },
        },
        "hint": "综合问答请用 POST /assistant/rag-answer（已含数据字典与可选 LLM）；本接口仅返回原始检索片段供自定义拼装。",
    }


class RagAnswerBody(BaseModel):
    """智慧运维：PDF + 司空 + 数据字典 + 可选能耗摘要；可选 OpenAI 兼容 LLM 归纳生成。"""

    query: str = Field(..., min_length=1)
    kb_limit: int = Field(8, ge=1, le=30)
    sikong_limit: int = Field(5, ge=1, le=20)
    use_llm: bool | None = Field(
        None,
        description="null=自动（已配置 LLM_API_BASE 则生成）；false=仅检索拼装；true=尝试 LLM",
    )
    building_id: str | None = Field(
        None,
        description="运维数据摘要按建筑筛选（可选）",
    )


@router.get("/llm-status")
def assistant_llm_status() -> dict[str, Any]:
    from app.config import settings
    from app.services.llm_openai_compat import llm_configured

    ok = llm_configured()
    return {
        "configured": ok,
        "api_base": settings.llm_api_base if ok else None,
        "model": settings.llm_model if ok else None,
    }


@router.get("/speech/status")
def assistant_speech_status() -> dict[str, Any]:
    """百度语音识别是否已在 backend/.env 配置。"""
    from app.config import settings

    ok = baidu_asr.baidu_asr_configured()
    return {
        "configured": ok,
        "provider": "baidu",
        "dev_pid": settings.baidu_speech_dev_pid if ok else None,
        "hint": None
        if ok
        else "请在 backend/.env 配置 BAIDU_SPEECH_API_KEY 与 BAIDU_SPEECH_SECRET_KEY（控制台创建语音技术应用后获取）",
    }


@router.post("/speech-to-text")
async def assistant_speech_to_text(
    file: UploadFile = File(..., description="16kHz 单声道 wav/pcm，或 amr/m4a"),
    format: str = Query("wav", pattern="^(wav|pcm|amr|m4a)$"),
    rate: int = Query(16000, ge=8000, le=48000),
) -> dict[str, Any]:
    """
    语音转文字：浏览器录音经后端转发至百度短语音识别，避免在前端暴露密钥。
    """
    if not baidu_asr.baidu_asr_configured():
        raise HTTPException(
            status_code=503,
            detail="百度语音未配置：请设置 BAIDU_SPEECH_API_KEY 与 BAIDU_SPEECH_SECRET_KEY",
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="上传的音频为空")

    try:
        result = baidu_asr.recognize_speech(audio_bytes, fmt=format, rate=rate)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"语音识别请求失败：{e}") from e

    return {
        "text": result["text"],
        "provider": "baidu",
        "format": format,
        "rate": rate,
    }


@router.post("/rag-answer")
def rag_answer_endpoint(body: RagAnswerBody) -> dict[str, Any]:
    """
    智慧运维综合问答：检索规范 PDF、司空语料、能耗数据字典；命中运维类问题时注入时段汇总与异常检测摘要。
    若设置 LLM_API_BASE（OpenAI 兼容），默认由轻量 LLM 基于上下文生成回答；失败或未配置时回退为检索拼装。
    """
    return rag_answer.unified_rag_answer(
        body.query,
        kb_limit=body.kb_limit,
        sikong_limit=body.sikong_limit,
        use_llm=body.use_llm,
        building_id=body.building_id,
    )
