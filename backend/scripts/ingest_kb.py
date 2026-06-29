# -*- coding: utf-8 -*-
"""
从「知识库所需文档」目录抽取 PDF 文本，切块后写入 SQLite FTS5，供 /api/kb/search 使用。
PNG 等扫描件无法直接抽字，将跳过（需 OCR 时另处理）。
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pypdf import PdfReader  # noqa: E402

from app.config import settings  # noqa: E402

CHUNK_SIZE = 900
CHUNK_OVERLAP = 120


def extract_pdf_text(path: Path) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    try:
        reader = PdfReader(str(path))
    except Exception as e:
        print(f"[skip] {path.name}: {e}")
        return pages
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            pages.append((i + 1, t))
    return pages


def chunk_text(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
    return chunks


def main() -> None:
    kb = settings.kb_root
    if not kb.is_dir():
        print(f"知识库目录不存在: {kb}")
        sys.exit(1)

    settings.kb_index_db.parent.mkdir(parents=True, exist_ok=True)
    if settings.kb_index_db.exists():
        settings.kb_index_db.unlink()

    conn = sqlite3.connect(settings.kb_index_db)
    conn.execute(
        """
        CREATE VIRTUAL TABLE kb_fts USING fts5(
            source_path,
            chunk_id,
            content,
            tokenize = 'unicode61'
        );
        """
    )

    pdfs = sorted(kb.glob("*.pdf"))
    total_chunks = 0
    for pdf in pdfs:
        pages = extract_pdf_text(pdf)
        if not pages:
            print(f"[empty] {pdf.name}")
            continue
        cid = 0
        sp = str(pdf.resolve())
        for page_no, ptext in pages:
            for part in chunk_text(ptext):
                cid += 1
                conn.execute(
                    "INSERT INTO kb_fts (source_path, chunk_id, content) VALUES (?, ?, ?)",
                    (sp, f"p{page_no}_c{cid}", part),
                )
                total_chunks += 1
        print(f"[ok] {pdf.name} -> chunks from {len(pages)} pages")

    conn.commit()
    conn.close()
    print(f"完成：{len(pdfs)} 个 PDF，共 {total_chunks} 条文本块 -> {settings.kb_index_db}")


if __name__ == "__main__":
    main()
