from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from app.config import settings


def _connect() -> sqlite3.Connection:
    settings.kb_index_db.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(settings.kb_index_db)


def is_index_ready() -> bool:
    return settings.kb_index_db.is_file() and settings.kb_index_db.stat().st_size > 0


def search_kb(query: str, limit: int = 15) -> dict[str, Any]:
    if not query.strip():
        return {"ready": is_index_ready(), "results": [], "message": "空查询"}
    if not is_index_ready():
        return {
            "ready": False,
            "results": [],
            "message": "知识库未索引：请在 backend 目录运行 python scripts/ingest_kb.py",
        }

    conn = _connect()
    cur = conn.cursor()
    q = query.strip()
    # FTS5：简单转义双引号
    safe = q.replace('"', " ")
    results: list[dict[str, Any]] = []
    try:
        cur.execute(
            """
            SELECT source_path, chunk_id,
                   snippet(kb_fts, 2, '【', '】', ' … ', 24) AS snip
            FROM kb_fts
            WHERE kb_fts MATCH ?
            LIMIT ?
            """,
            (safe, limit),
        )
        for row in cur.fetchall():
            results.append(
                {
                    "source_path": row[0],
                    "chunk_id": row[1],
                    "snippet": row[2],
                    "score": None,
                }
            )
    except sqlite3.OperationalError:
        # 单关键词失败时退回 LIKE
        like = f"%{q}%"
        cur.execute(
            """
            SELECT source_path, chunk_id, substr(content, 1, 400) AS snip
            FROM kb_fts
            WHERE content LIKE ?
            LIMIT ?
            """,
            (like, limit),
        )
        for row in cur.fetchall():
            results.append(
                {
                    "source_path": row[0],
                    "chunk_id": row[1],
                    "snippet": row[2],
                    "score": None,
                }
            )
    conn.close()

    return {"ready": True, "query": q, "count": len(results), "results": results}


def rag_stub_answer(query: str, limit: int = 5) -> dict[str, Any]:
    """演示：检索片段 + 模板回复（非真实 LLM）。"""
    r = search_kb(query, limit=limit)
    chunks = r.get("results") or []
    if not chunks:
        return {
            "query": query,
            "answer": "未在知识库中找到相关内容，请先运行索引脚本或更换关键词。",
            "citations": [],
        }

    lines = []
    for i, c in enumerate(chunks[:5], 1):
        src = Path(c["source_path"]).name
        snip = re.sub(r"【|】", "", str(c.get("snippet", "")))
        lines.append(f"[{i}] 《{src}》 {snip}")

    body = "\n".join(lines)
    answer = (
        "根据知识库检索，与问题相关的规范片段如下（演示级拼接，非大模型生成）：\n\n" + body
    )
    citations = [{"source": c["source_path"], "chunk_id": c["chunk_id"]} for c in chunks[:5]]
    return {"query": query, "answer": answer, "citations": citations}
