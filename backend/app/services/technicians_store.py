"""维修员资源（融合课设 technicians 表，演示级 SQLite）。"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "technicians.sqlite"

_SEED = (
    ("张师傅", "广东省深圳市", "HIGH", "13800001001", 1, "tech1"),
    ("李师傅", "广东省广州市", "MEDIUM", "13800001002", 0, "tech2"),
    ("王师傅", "广东省东莞市", "MEDIUM", "13800001003", 1, "tech3"),
)


def _sync_technician_usernames(conn: sqlite3.Connection) -> None:
    """与 users 表 tech1/tech2/tech3 对齐（兼容旧库仅有 ops 绑定张师傅的情况）。"""
    mapping = {1: "tech1", 2: "tech2", 3: "tech3"}
    for tech_id, username in mapping.items():
        conn.execute("UPDATE technicians SET username = ? WHERE id = ?", (username, tech_id))
    conn.commit()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS technicians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            region TEXT NOT NULL,
            skill_level TEXT NOT NULL DEFAULT 'MEDIUM',
            contact_phone TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            load_count INTEGER NOT NULL DEFAULT 0,
            username TEXT
        )
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(technicians)").fetchall()}
    if "username" not in cols:
        conn.execute("ALTER TABLE technicians ADD COLUMN username TEXT")
        conn.commit()
    cur = conn.execute("SELECT COUNT(*) AS n FROM technicians")
    if int(cur.fetchone()["n"]) == 0:
        for name, region, skill, phone, load, username in _SEED:
            conn.execute(
                """
                INSERT INTO technicians (name, region, skill_level, contact_phone, active, load_count, username)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (name, region, skill, phone, load, username),
            )
        conn.commit()
    else:
        _sync_technician_usernames(conn)
        _migrate_technician_regions(conn)
    return conn


def _migrate_technician_regions(conn: sqlite3.Connection) -> None:
    """旧库「北区/南区」→ 省市区服务区域。"""
    mapping = {
        "北区": "广东省深圳市",
        "南区": "广东省广州市",
        "东区": "广东省东莞市",
        "西区": "广东省佛山市",
    }
    for old, new in mapping.items():
        conn.execute("UPDATE technicians SET region = ? WHERE region = ?", (new, old))
    conn.commit()


def find_by_username(username: str) -> dict[str, Any] | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM technicians WHERE username = ? AND active = 1",
        (username,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_technicians(active_only: bool = True) -> list[dict[str, Any]]:
    conn = _connect()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM technicians WHERE active = 1 ORDER BY load_count ASC, id ASC"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM technicians ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_technician(tech_id: int) -> dict[str, Any] | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM technicians WHERE id = ?", (tech_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_profile(tech_id: int, *, region: str, skill_level: str, contact_phone: str | None) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE technicians SET region = ?, skill_level = ?, contact_phone = ? WHERE id = ?",
        (region, skill_level, contact_phone, tech_id),
    )
    conn.commit()
    conn.close()


def adjust_load(tech_id: int | None, delta: int) -> None:
    if not tech_id:
        return
    conn = _connect()
    row = conn.execute("SELECT load_count FROM technicians WHERE id = ?", (tech_id,)).fetchone()
    if not row:
        conn.close()
        return
    new_load = max(0, int(row["load_count"]) + delta)
    conn.execute("UPDATE technicians SET load_count = ? WHERE id = ?", (new_load, tech_id))
    conn.commit()
    conn.close()


def recalculate_loads_from_incidents() -> None:
    """按在途工单重新统计各维修员负载，避免删除工单后负载残留。"""
    from app.services import workorder_state_machine as sm

    load_statuses = (
        sm.WO_DISPATCHED,
        sm.WO_ACCEPTED,
        sm.WO_IN_PROGRESS,
        sm.WO_ON_HOLD,
        sm.WO_PENDING,
    )
    placeholders = ",".join("?" for _ in load_statuses)
    inc = sqlite3.connect(DB_PATH.parent / "incidents.sqlite")
    inc.row_factory = sqlite3.Row
    counts: dict[int, int] = {}
    try:
        rows = inc.execute(
            f"""
            SELECT technician_id, COUNT(*) AS c
            FROM incidents
            WHERE technician_id IS NOT NULL AND wo_status IN ({placeholders})
            GROUP BY technician_id
            """,
            load_statuses,
        ).fetchall()
        counts = {int(r["technician_id"]): int(r["c"]) for r in rows}
    finally:
        inc.close()

    conn = _connect()
    conn.execute("UPDATE technicians SET load_count = 0")
    for tech_id, cnt in counts.items():
        conn.execute("UPDATE technicians SET load_count = ? WHERE id = ?", (cnt, tech_id))
    conn.commit()
    conn.close()
