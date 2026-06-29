from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services import workorder_state_machine as sm

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "incidents.sqlite"

_WO_COLUMNS: dict[str, str] = {
    "wo_status": "TEXT NOT NULL DEFAULT 'NEW'",
    "order_no": "TEXT",
    "category": "TEXT NOT NULL DEFAULT 'HVAC'",
    "priority": "TEXT NOT NULL DEFAULT 'MEDIUM'",
    "technician_id": "INTEGER",
    "technician_name": "TEXT",
    "invited_technician_id": "INTEGER",
    "requester": "TEXT",
    "location": "TEXT",
    "province": "TEXT",
    "city": "TEXT",
    "district": "TEXT",
    "address_detail": "TEXT",
    "campus": "TEXT",
    "floor": "TEXT",
    "room": "TEXT",
    "contact_phone": "TEXT",
    "description": "TEXT",
    "expected_completion_type": "TEXT DEFAULT 'ASAP'",
    "expected_completion_at": "TEXT",
    "attachment_filename": "TEXT",
    "hold_reason": "TEXT",
    "reject_reason": "TEXT",
}


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
            source TEXT NOT NULL DEFAULT 'manual',
            detail TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS incident_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            from_status TEXT NOT NULL,
            to_status TEXT NOT NULL,
            operator_name TEXT NOT NULL,
            operator_role TEXT NOT NULL,
            remark TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(incidents)").fetchall()}
    if "source" not in cols:
        conn.execute("ALTER TABLE incidents ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
    for col, ddl in _WO_COLUMNS.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE incidents ADD COLUMN {col} {ddl}")
    conn.execute(
        """
        UPDATE incidents SET wo_status = CASE status
            WHEN 'open' THEN 'NEW'
            WHEN 'in_progress' THEN 'IN_PROGRESS'
            WHEN 'resolved' THEN 'PENDING_CONFIRMATION'
            WHEN 'closed' THEN 'COMPLETED'
            ELSE COALESCE(wo_status, 'NEW')
        END
        WHERE wo_status IS NULL OR wo_status = 'NEW'
        """
    )
    conn.commit()
    return conn


def _gen_order_no(incident_id: int) -> str:
    day = datetime.now().strftime("%Y%m%d")
    return f"EMS-{day}-{incident_id:04d}"


def compose_location(
    province: str | None = None,
    city: str | None = None,
    district: str | None = None,
    address_detail: str | None = None,
    building_id: str | None = None,
    floor: str | None = None,
    room: str | None = None,
    campus: str | None = None,
) -> str:
    parts = [str(p).strip() for p in (province, city, district, address_detail) if p and str(p).strip()]
    if parts:
        return "".join(parts)
    legacy = [str(p).strip() for p in (campus, building_id, floor, room) if p and str(p).strip()]
    return " ".join(legacy)


def _severity_to_priority(severity: str) -> str:
    m = {"critical": "URGENT", "high": "HIGH", "medium": "MEDIUM", "low": "LOW"}
    return m.get(severity, "MEDIUM")


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    wo = sm.normalize_wo_status(row.get("wo_status"), row.get("status"))
    out = dict(row)
    out["wo_status"] = wo
    out["status"] = wo
    if not out.get("order_no"):
        out["order_no"] = _gen_order_no(int(out["id"]))
    out["category"] = out.get("category") or "HVAC"
    out["priority"] = out.get("priority") or _severity_to_priority(str(out.get("severity") or "medium"))
    if out.get("building_id") and not out.get("location"):
        out["location"] = str(out["building_id"])
    composed = compose_location(
        out.get("province"),
        out.get("city"),
        out.get("district"),
        out.get("address_detail"),
        out.get("building_id"),
        out.get("floor"),
        out.get("room"),
        out.get("campus"),
    )
    if composed:
        out["location"] = composed
    return out


def incident_summary() -> dict[str, Any]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT wo_status, status, COUNT(*) AS n FROM incidents GROUP BY wo_status, status")
    by_wo: dict[str, int] = {}
    for r in cur.fetchall():
        wo = sm.normalize_wo_status(r["wo_status"], r["status"])
        by_wo[wo] = by_wo.get(wo, 0) + int(r["n"])
    conn.close()
    for s in (
        sm.WO_NEW,
        sm.WO_DISPATCHED,
        sm.WO_ACCEPTED,
        sm.WO_IN_PROGRESS,
        sm.WO_ON_HOLD,
        sm.WO_PENDING,
        sm.WO_COMPLETED,
        sm.WO_REJECTED,
        sm.WO_CANCELLED,
        sm.WO_VISION_DRAFT,
    ):
        by_wo.setdefault(s, 0)
    pending = (
        by_wo.get(sm.WO_NEW, 0)
        + by_wo.get(sm.WO_DISPATCHED, 0)
        + by_wo.get(sm.WO_ACCEPTED, 0)
        + by_wo.get(sm.WO_IN_PROGRESS, 0)
        + by_wo.get(sm.WO_ON_HOLD, 0)
    )
    total = sum(by_wo.values())
    return {"by_status": by_wo, "pending": pending, "total": total}


def get_incident(incident_id: int) -> dict[str, Any] | None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    row = cur.fetchone()
    conn.close()
    return _normalize_row(dict(row)) if row else None


def list_incidents(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()
    if status:
        cur.execute(
            """
            SELECT * FROM incidents
            WHERE wo_status = ? OR status = ?
            ORDER BY id DESC LIMIT ?
            """,
            (status, sm.WO_TO_LEGACY.get(status, status), limit),
        )
    else:
        cur.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,))
    rows = [_normalize_row(dict(r)) for r in cur.fetchall()]
    conn.close()
    return rows


def list_incidents_for_user(
    role: str | None,
    username: str | None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    rows = list_incidents(status=status, limit=limit)
    if role == "requester" and username:
        return [r for r in rows if (r.get("requester") or "") == username]
    if role == "ops":
        pool = {sm.WO_NEW, sm.WO_DISPATCHED, sm.WO_VISION_DRAFT}
        return [
            r
            for r in rows
            if r.get("wo_status") in pool or r.get("technician_id")
        ]
    return rows


def create_incident(
    title: str,
    severity: str = "medium",
    status: str = "open",
    building_id: str | None = None,
    detail: str | None = None,
    source: str = "manual",
    requester: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    location: str | None = None,
    campus: str | None = None,
    floor: str | None = None,
    room: str | None = None,
    contact_phone: str | None = None,
    description: str | None = None,
    expected_completion_type: str | None = None,
    expected_completion_at: str | None = None,
    attachment_filename: str | None = None,
    wo_status: str | None = None,
    province: str | None = None,
    city: str | None = None,
    district: str | None = None,
    address_detail: str | None = None,
) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    wo = wo_status if wo_status in sm._ALL_WO else sm.WO_NEW
    legacy = sm.WO_TO_LEGACY.get(wo, "open")
    cat = category or {"stats": "HVAC", "vision": "ELECTRIC", "ops": "HVAC"}.get(source, "OTHER")
    pri = priority or _severity_to_priority(severity)
    loc = location or compose_location(province, city, district, address_detail, building_id, floor, room, campus) or building_id
    desc = description or detail or ""

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO incidents (
            title, building_id, severity, status, source, detail,
            wo_status, category, priority, requester, location,
            province, city, district, address_detail,
            campus, floor, room, contact_phone, description,
            expected_completion_type, expected_completion_at, attachment_filename,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            building_id,
            severity,
            legacy,
            source,
            detail or desc,
            wo,
            cat,
            pri,
            requester,
            loc,
            province,
            city,
            district,
            address_detail,
            campus,
            floor,
            room,
            contact_phone,
            desc,
            expected_completion_type or "ASAP",
            expected_completion_at,
            attachment_filename,
            now,
            now,
        ),
    )
    iid = int(cur.lastrowid)
    order_no = _gen_order_no(iid)
    cur.execute("UPDATE incidents SET order_no = ? WHERE id = ?", (order_no, iid))
    conn.commit()
    cur.execute("SELECT * FROM incidents WHERE id = ?", (iid,))
    row = dict(cur.fetchone())
    conn.close()

    add_history(iid, "—", wo, requester or "系统", "报修", f"创建工单（来源：{source}）")
    return _normalize_row(row)


def delete_incident(incident_id: int) -> bool:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM incident_history WHERE incident_id = ?", (incident_id,))
    cur.execute("DELETE FROM incidents WHERE id = ?", (incident_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    if deleted:
        from app.services import technicians_store

        technicians_store.recalculate_loads_from_incidents()
    return deleted


def update_incident_fields(incident_id: int, **fields: Any) -> dict[str, Any] | None:
    allowed = {
        "title",
        "building_id",
        "severity",
        "status",
        "source",
        "detail",
        "wo_status",
        "order_no",
        "category",
        "priority",
        "technician_id",
        "technician_name",
        "invited_technician_id",
        "requester",
        "location",
        "province",
        "city",
        "district",
        "address_detail",
        "campus",
        "floor",
        "room",
        "contact_phone",
        "description",
        "expected_completion_type",
        "expected_completion_at",
        "attachment_filename",
        "hold_reason",
        "reject_reason",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_incident(incident_id)
    updates["updated_at"] = datetime.now().isoformat(timespec="seconds")
    parts = [f"{k} = ?" for k in updates]
    values = list(updates.values()) + [incident_id]
    conn = _connect()
    cur = conn.cursor()
    cur.execute(f"UPDATE incidents SET {', '.join(parts)} WHERE id = ?", values)
    conn.commit()
    cur.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    row = cur.fetchone()
    conn.close()
    return _normalize_row(dict(row)) if row else None


def update_incident(
    incident_id: int,
    status: str | None = None,
    severity: str | None = None,
    detail: str | None = None,
    title: str | None = None,
    building_id: str | None = None,
    source: str | None = None,
) -> dict[str, Any] | None:
    extra: dict[str, Any] = {}
    if title is not None:
        extra["title"] = title
    if building_id is not None:
        extra["building_id"] = building_id
        extra["location"] = building_id
    if severity is not None:
        extra["severity"] = severity
    if detail is not None:
        extra["detail"] = detail
    if source is not None:
        extra["source"] = source
    if status is not None:
        if status in sm._ALL_WO:
            extra["wo_status"] = status
            extra["status"] = sm.WO_TO_LEGACY.get(status, "open")
        else:
            extra["status"] = status
            extra["wo_status"] = sm.LEGACY_TO_WO.get(status, sm.WO_NEW)
    return update_incident_fields(incident_id, **extra)


def add_history(
    incident_id: int,
    from_status: str,
    to_status: str,
    operator_name: str,
    operator_role: str,
    remark: str | None = None,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn = _connect()
    conn.execute(
        """
        INSERT INTO incident_history
        (incident_id, from_status, to_status, operator_name, operator_role, remark, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (incident_id, from_status, to_status, operator_name, operator_role, remark, now),
    )
    conn.commit()
    conn.close()


def list_history(incident_id: int) -> list[dict[str, Any]]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM incident_history WHERE incident_id = ? ORDER BY id ASC",
        (incident_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
