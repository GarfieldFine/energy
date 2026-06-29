from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "incidents.sqlite"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            building_id TEXT,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return conn


def incident_summary() -> dict[str, Any]:
    """各状态计数 + 待处理（open + in_progress）。"""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) AS n FROM incidents GROUP BY status")
    by_status: dict[str, int] = {str(r["status"]): int(r["n"]) for r in cur.fetchall()}
    conn.close()
    for s in ("open", "in_progress", "resolved", "closed"):
        by_status.setdefault(s, 0)
    pending = by_status.get("open", 0) + by_status.get("in_progress", 0)
    total = sum(by_status.values())
    return {"by_status": by_status, "pending": pending, "total": total}


def get_incident(incident_id: int) -> dict[str, Any] | None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_incidents(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()
    if status:
        cur.execute(
            "SELECT * FROM incidents WHERE status = ? ORDER BY id DESC LIMIT ?",
            (status, limit),
        )
    else:
        cur.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def create_incident(
    title: str,
    severity: str = "medium",
    status: str = "open",
    building_id: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO incidents (title, building_id, severity, status, detail, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (title, building_id, severity, status, detail, now, now),
    )
    iid = int(cur.lastrowid)
    conn.commit()
    cur.execute("SELECT * FROM incidents WHERE id = ?", (iid,))
    row = dict(cur.fetchone())
    conn.close()
    return row


def update_incident(
    incident_id: int,
    status: str | None = None,
    severity: str | None = None,
    detail: str | None = None,
    title: str | None = None,
    building_id: str | None = None,
) -> dict[str, Any] | None:
    fields: list[str] = []
    values: list[Any] = []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if building_id is not None:
        fields.append("building_id = ?")
        values.append(building_id)
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if severity is not None:
        fields.append("severity = ?")
        values.append(severity)
    if detail is not None:
        fields.append("detail = ?")
        values.append(detail)
    fields.append("updated_at = ?")
    values.append(datetime.now().isoformat(timespec="seconds"))
    values.append(incident_id)

    conn = _connect()
    cur = conn.cursor()
    cur.execute(f"UPDATE incidents SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    cur.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_incident(incident_id: int) -> bool:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM incidents WHERE id = ?", (incident_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

