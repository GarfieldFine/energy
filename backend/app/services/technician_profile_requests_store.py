"""维修员档案修改申请（演示 SQLite）。"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services import technicians_store

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "tech_profile_requests.sqlite"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tech_profile_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            technician_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            technician_name TEXT NOT NULL,
            region TEXT NOT NULL,
            skill_level TEXT NOT NULL,
            contact_phone TEXT,
            proof_attachment_filename TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            reject_reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tech_profile_requests)")}
    if "proof_attachment_filename" not in cols:
        conn.execute("ALTER TABLE tech_profile_requests ADD COLUMN proof_attachment_filename TEXT")
        conn.commit()


def _to_api(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "technicianId": int(row["technician_id"]),
        "username": row["username"],
        "technicianName": row["technician_name"],
        "region": row["region"],
        "skillLevel": row["skill_level"],
        "contactPhone": row["contact_phone"],
        "attachmentFilename": row["proof_attachment_filename"],
        "status": row["status"],
        "rejectReason": row["reject_reason"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def submit(
    username: str,
    region: str,
    skill_level: str,
    contact_phone: str,
    attachment_filename: str,
) -> dict[str, Any]:
    tech = technicians_store.find_by_username(username)
    if not tech:
        raise ValueError("未找到维修档案")
    proof = (attachment_filename or "").strip()
    if not proof:
        raise ValueError("请上传资质证明材料")
    conn = _connect()
    pending = conn.execute(
        "SELECT id FROM tech_profile_requests WHERE username = ? AND status = 'PENDING'",
        (username,),
    ).fetchone()
    if pending:
        conn.close()
        raise ValueError("已有待审批的档案修改申请")
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tech_profile_requests
        (technician_id, username, technician_name, region, skill_level, contact_phone,
         proof_attachment_filename, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
        """,
        (tech["id"], username, tech["name"], region, skill_level, contact_phone, proof, now, now),
    )
    conn.commit()
    rid = int(cur.lastrowid)
    row = conn.execute("SELECT * FROM tech_profile_requests WHERE id = ?", (rid,)).fetchone()
    conn.close()
    return _to_api(row)


def my_pending(username: str) -> dict[str, Any] | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM tech_profile_requests WHERE username = ? AND status = 'PENDING' ORDER BY id DESC LIMIT 1",
        (username,),
    ).fetchone()
    conn.close()
    return _to_api(row) if row else None


def list_pending() -> list[dict[str, Any]]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM tech_profile_requests WHERE status = 'PENDING' ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [_to_api(r) for r in rows]


def approve(request_id: int) -> dict[str, Any]:
    conn = _connect()
    row = conn.execute("SELECT * FROM tech_profile_requests WHERE id = ?", (request_id,)).fetchone()
    if not row or row["status"] != "PENDING":
        conn.close()
        raise ValueError("申请不存在或已处理")
    now = datetime.now().isoformat(timespec="seconds")
    technicians_store.update_profile(
        int(row["technician_id"]),
        region=str(row["region"]),
        skill_level=str(row["skill_level"]),
        contact_phone=row["contact_phone"],
    )
    conn.execute(
        "UPDATE tech_profile_requests SET status = 'APPROVED', updated_at = ? WHERE id = ?",
        (now, request_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tech_profile_requests WHERE id = ?", (request_id,)).fetchone()
    conn.close()
    return _to_api(row)


def reject(request_id: int, reason: str | None) -> dict[str, Any]:
    conn = _connect()
    row = conn.execute("SELECT * FROM tech_profile_requests WHERE id = ?", (request_id,)).fetchone()
    if not row or row["status"] != "PENDING":
        conn.close()
        raise ValueError("申请不存在或已处理")
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE tech_profile_requests SET status = 'REJECTED', reject_reason = ?, updated_at = ? WHERE id = ?",
        (reason or "未通过审批", now, request_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tech_profile_requests WHERE id = ?", (request_id,)).fetchone()
    conn.close()
    return _to_api(row)
