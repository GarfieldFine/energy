"""
智慧运维 RAG：规范 PDF + 司空语料 + 数据字典检索 + 可选运维数据摘要；
可选 OpenAI 兼容 LLM 生成；失败回退检索拼装。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.config import settings
from app.services import kb_search, sikong_qa
from app.services.llm_openai_compat import chat_completion, llm_configured
from app.services.ops_context import (
    format_dictionary_for_prompt,
    ops_data_bundle,
    search_data_dictionary,
)


def _clean_snip(text: str) -> str:
    t = re.sub(r"【|】", "", str(text or ""))
    return re.sub(r"\s+", " ", t).strip()


def _build_rag_core(query: str, kb_limit: int, sikong_limit: int) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "query": query,
            "answer": "查询内容为空。",
            "citations": [],
            "retrieval": {"pdf": {}, "sikong": {}},
        }

    pdf = kb_search.search_kb(q, limit=kb_limit)
    sik = sikong_qa.search_sikong(q, limit=sikong_limit)
    pdf_items = pdf.get("results") or []
    sik_items = sik.get("results") or []
    citations: list[dict[str, Any]] = []
    blocks: list[str] = []

    if not kb_search.is_index_ready():
        blocks.append(
            "【一、规范与标准条文】\n"
            "知识库未建立索引：请在 backend 目录执行 python scripts/ingest_kb.py 后重试。\n"
        )
    elif pdf_items:
        lines = ["【一、规范与标准条文】", "以下为检索到的条文片段（节选）："]
        for i, c in enumerate(pdf_items, 1):
            src = Path(c["source_path"]).name
            snip = _clean_snip(c.get("snippet", ""))
            lines.append(f"{i}. 《{src}》 {snip}")
            citations.append(
                {"type": "pdf", "source": c["source_path"], "chunk_id": c.get("chunk_id")}
            )
        blocks.append("\n".join(lines))
    else:
        blocks.append(
            "【一、规范与标准条文】\n"
            "未命中已索引 PDF。可尝试更换关键词或补充知识库 PDF 后重新索引。\n"
        )

    if sik.get("message") and not sik_items:
        blocks.append(
            "【二、领域问答参考（司空语料）】\n"
            f"{sik.get('message', '司空语料未就绪或路径无效。')}\n"
        )
    elif sik_items:
        lines = ["【二、领域问答参考（司空语料）】", "以下为与问题相关的问答条目（节选）："]
        for i, it in enumerate(sik_items, 1):
            iq = (it.get("input") or "").strip()
            oa = (it.get("output") or "").strip()
            iq_short = iq[:200] + ("…" if len(iq) > 200 else "")
            oa_short = oa[:500] + ("…" if len(oa) > 500 else "")
            lines.append(f"{i}. 问：{iq_short}\n   答：{oa_short}")
            citations.append({"type": "sikong", "input_preview": iq[:120], "output_preview": oa[:120]})
        blocks.append("\n".join(lines))
    else:
        blocks.append(
            "【二、领域问答参考（司空语料）】\n"
            "未命中相关条目。可尝试拆分关键词或确认已生成 sikong_sft_all.jsonl。\n"
        )

    answer = "\n\n".join(blocks).strip()
    if not pdf_items and not sik_items and kb_search.is_index_ready() and sik.get("ready"):
        answer = (
            "未在规范知识库与司空语料中检索到与问题直接相关的内容。\n"
            "建议：① 换用设备/标准编号/术语等更具体的关键词；② 确认 PDF 已入库并完成索引；③ 确认司空 jsonl 路径正确。\n\n"
            + answer
        )

    retrieval = {
        "pdf": {
            "ready": pdf.get("ready", kb_search.is_index_ready()),
            "count": len(pdf_items),
            "message": pdf.get("message"),
        },
        "sikong": {
            "ready": sik.get("ready"),
            "count": len(sik_items),
            "total_indexed": sik.get("total_indexed"),
            "message": sik.get("message"),
        },
    }
    return {"query": q, "answer": answer, "citations": citations, "retrieval": retrieval}


def _append_ops_sections(
    base_answer: str,
    *,
    dd_result: dict[str, Any],
    ops_bundle: dict[str, Any],
) -> str:
    extra: list[str] = []
    if dd_result.get("ready") and (dd_result.get("items") or []):
        extra.append(format_dictionary_for_prompt(dd_result["items"]))
    if ops_bundle.get("included") and ops_bundle.get("summary_text"):
        extra.append(ops_bundle["summary_text"])
    if not extra:
        return base_answer
    return base_answer + "\n\n" + "\n\n".join(extra)


def unified_rag_answer(
    query: str,
    kb_limit: int = 8,
    sikong_limit: int = 5,
    *,
    use_llm: bool | None = None,
    building_id: str | None = None,
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "query": query,
            "mode": "rag_only",
            "answer": "查询内容为空。",
            "citations": [],
            "retrieval": {"pdf": {}, "sikong": {}, "data_dictionary": {}, "ops_data": {}},
        }

    core = _build_rag_core(q, kb_limit, sikong_limit)
    dd_result = search_data_dictionary(q, limit=12)
    ops_bundle = ops_data_bundle(q, building_id=building_id)

    merged_citations = list(core["citations"])
    for i, row in enumerate(dd_result.get("items") or [], 1):
        merged_citations.append({"type": "data_dictionary", "row_index": i, "fields": row})

    retrieval = dict(core["retrieval"])
    retrieval["data_dictionary"] = {
        "ready": dd_result.get("ready"),
        "count": dd_result.get("count", 0),
        "message": dd_result.get("message"),
    }
    retrieval["ops_data"] = {
        "included": ops_bundle.get("included", False),
        "building_id": building_id,
    }

    baseline = _append_ops_sections(core["answer"], dd_result=dd_result, ops_bundle=ops_bundle)

    want_llm = use_llm is not False and (use_llm is True or llm_configured())

    if not want_llm:
        desc = (
            "检索增强拼装：规范 PDF + 司空语料 + 数据字典"
            + (" + 运维数据摘要" if ops_bundle.get("included") else "")
            + "。"
        )
        if not llm_configured():
            desc += " 未配置 LLM_API_BASE，未调用大模型生成。"
        return {
            "query": q,
            "mode": "rag_only",
            "description": desc,
            "answer": baseline,
            "citations": merged_citations,
            "retrieval": retrieval,
            "llm": {"used": False, "model": None, "error": None},
        }

    ctx_parts: list[str] = []
    if ops_bundle.get("included") and ops_bundle.get("summary_text"):
        ctx_parts.append(ops_bundle["summary_text"])
    if dd_result.get("ready") and (dd_result.get("items") or []):
        ctx_parts.append(format_dictionary_for_prompt(dd_result["items"]))
    ctx_parts.append("【检索到的规范与司空参考（节选）】\n" + core["answer"])
    full_context = "\n\n".join(ctx_parts)
    if len(full_context) > 14000:
        full_context = full_context[:14000] + "\n…（上下文已截断）"

    system = (
        "你是建筑能源智慧运维助手。请严格依据用户问题与下列「上下文」作答；"
        "若上下文不足以得出结论，请明确说明，不要编造数值或条文。"
        "回答使用简洁中文，可分点。若上下文中含「实时数据摘要」，可在分析能耗、异常原因时引用其中的数字。"
        "不要复述冗长的原文列表，应归纳、对比与给出可执行建议。"
    )
    user_msg = f"用户问题：\n{q}\n\n--- 上下文 ---\n{full_context}"

    content, err = chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        temperature=0.35,
        max_tokens=2048,
    )

    if content and not err:
        return {
            "query": q,
            "mode": "rag_llm",
            "description": (
                f"RAG + 轻量 LLM 生成（模型：{settings.llm_model}）。 "
                "回答由模型基于检索上下文归纳，请核对引用与数据摘要。"
            ),
            "answer": content,
            "citations": merged_citations,
            "retrieval": retrieval,
            "llm": {"used": True, "model": settings.llm_model, "error": None},
            "baseline_answer": baseline,
        }

    desc = "检索增强拼装（LLM 不可用或失败，已回退）。 "
    if err:
        desc += err[:200]
    return {
        "query": q,
        "mode": "rag_only",
        "description": desc,
        "answer": baseline,
        "citations": merged_citations,
        "retrieval": retrieval,
        "llm": {"used": False, "model": None, "error": err},
        "baseline_answer": baseline,
    }
