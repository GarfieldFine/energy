"""演示用户库（SQLite）：登录、改密、管理员账号维护。"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.services import auth_service

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "users.sqlite"

EMS_TO_WO_API_ROLE = {
    "admin": "ADMIN",
    "ops": "TECHNICIAN",
    "requester": "REQUESTER",
    "energy": "ENERGY",
}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            builtin INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cur = conn.execute("SELECT COUNT(*) AS n FROM users")
    if int(cur.fetchone()["n"]) == 0:
        for username, row in auth_service.builtin_users_seed().items():
            conn.execute(
                """
                INSERT INTO users (username, password, display_name, role, active, builtin)
                VALUES (?, ?, ?, ?, 1, 1)
                """,
                (username, row["password"], row["display_name"], row["role"]),
            )
        conn.commit()
    else:
        _migrate_technician_accounts(conn)
    return conn


def _migrate_technician_accounts(conn: sqlite3.Connection) -> None:
    """旧库仅有 ops 单账号时，补齐 tech1/tech2/tech3 并绑定三位师傅。"""
    seed = auth_service.builtin_users_seed()
    ops_row = conn.execute("SELECT * FROM users WHERE username = 'ops'").fetchone()
    ops_pwd = ops_row["password"] if ops_row else None

    for username in ("tech1", "tech2", "tech3"):
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            continue
        meta = seed[username]
        pwd = ops_pwd if username == "tech1" and ops_pwd else meta["password"]
        conn.execute(
            """
            INSERT INTO users (username, password, display_name, role, active, builtin)
            VALUES (?, ?, ?, ?, 1, 1)
            """,
            (username, pwd, meta["display_name"], meta["role"]),
        )

    if ops_row and conn.execute("SELECT id FROM users WHERE username = 'tech1'").fetchone():
        conn.execute("DELETE FROM users WHERE username = 'ops'")

    if conn.execute("SELECT id FROM users WHERE username = 'req1'").fetchone():
        conn.execute("DELETE FROM users WHERE username = 'requester'")

    for dup in ():
        rows = conn.execute(
            "SELECT id FROM users WHERE username = ? ORDER BY id",
            (dup,),
        ).fetchall()
        if len(rows) > 1:
            for r in rows[1:]:
                conn.execute("DELETE FROM users WHERE id = ?", (r["id"],))

    conn.commit()


def _row_to_api(row: sqlite3.Row) -> dict[str, Any]:
    role = str(row["role"])
    return {
        "id": int(row["id"]),
        "username": row["username"],
        "displayName": row["display_name"],
        "role": EMS_TO_WO_API_ROLE.get(role, role.upper()),
        "emsRole": role,
        "active": bool(row["active"]),
    }


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    u = (username or "").strip()
    p = password or ""
    # 兼容旧演示账号 ops → 张师傅 tech1
    if u == "ops":
        u = "tech1"
        if p == "ops123":
            p = auth_service.builtin_users_seed()["tech1"]["password"]
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? AND active = 1",
        (u,),
    ).fetchone()
    conn.close()
    if not row or row["password"] != p:
        return None
    role = str(row["role"])
    return {
        "username": row["username"],
        "role": role,
        "display_name": row["display_name"],
        "role_label": auth_service.ROLE_LABELS.get(role, role),
    }


def list_users() -> list[dict[str, Any]]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    conn.close()
    return [_row_to_api(r) for r in rows]


def list_requesters() -> list[dict[str, Any]]:
    return [u for u in list_users() if u.get("emsRole") == "requester" and u.get("active")]


def get_by_id(user_id: int) -> dict[str, Any] | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return _row_to_api(row) if row else None


def get_by_username(username: str) -> dict[str, Any] | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return _row_to_api(row) if row else None


def change_password(username: str, old_password: str, new_password: str) -> None:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("用户不存在")
    if row["password"] != old_password:
        conn.close()
        raise ValueError("原密码错误")
    if not new_password or len(new_password) < 3:
        conn.close()
        raise ValueError("新密码至少 3 位")
    conn.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, username))
    conn.commit()
    conn.close()


def update_user(user_id: int, *, active: bool | None = None) -> dict[str, Any]:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("用户不存在")
    if str(row["role"]) == "admin" and active is False:
        conn.close()
        raise ValueError("不能停用管理员账号")
    if active is not None:
        conn.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))
        conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return _row_to_api(row)


def reset_password(user_id: int, password: str) -> None:
    pwd = password or "123456"
    conn = _connect()
    row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("用户不存在")
    conn.execute("UPDATE users SET password = ? WHERE id = ?", (pwd, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id: int, operator_username: str) -> None:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("用户不存在")
    if str(row["role"]) == "admin":
        conn.close()
        raise ValueError("不能删除管理员账号")
    if row["username"] == operator_username:
        conn.close()
        raise ValueError("不能删除当前登录账号")
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
