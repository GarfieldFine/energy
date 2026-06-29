"""
能耗外部 API 定时同步：拉取 JSON/CSV → 合并去重 → 落盘 imported CSV → 刷新内存缓存。
"""
from __future__ import annotations

import asyncio
import io
import logging
import threading
from datetime import datetime, timezone
from typing import Any

import httpx
import pandas as pd

from app.config import settings
from app.services.dataset_paths import IMPORT_DIR, energy_csv_path
from app.services.dataset_upload import ENERGY_METRICS, ENERGY_REQUIRED
from app.services.energy_store import clear_data_caches, load_energy

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_sync_lock = threading.Lock()
_state: dict[str, Any] = {
    "enabled": False,
    "running": False,
    "last_sync_at": None,
    "last_success_at": None,
    "last_error": None,
    "consecutive_failures": 0,
    "last_rows_incoming": 0,
    "last_rows_added": 0,
    "last_rows_updated": 0,
    "last_rows_total": 0,
    "sync_count": 0,
    "success_count": 0,
}

_loop_task: asyncio.Task | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_sync_state() -> dict[str, Any]:
    with _lock:
        out = dict(_state)
    out["energy_api_url"] = settings.energy_api_url
    out["sync_interval_sec"] = settings.energy_sync_interval_sec
    if out["enabled"] and out["last_success_at"]:
        out["status"] = "ok" if out["consecutive_failures"] == 0 else "degraded"
    elif out["enabled"] and out["last_error"] and not out["last_success_at"]:
        out["status"] = "error"
    elif out["enabled"] and out["running"]:
        out["status"] = "syncing"
    elif out["enabled"]:
        out["status"] = "idle"
    else:
        out["status"] = "disabled"
    return out


def _set_state(**kwargs: Any) -> None:
    with _lock:
        _state.update(kwargs)


def _normalize_energy_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    cols = set(df.columns)
    missing = ENERGY_REQUIRED - cols
    if missing:
        raise ValueError(f"缺少必填列：{', '.join(sorted(missing))}")
    if not ENERGY_METRICS & cols:
        raise ValueError(f"至少需包含一类能耗/环境指标列：{', '.join(sorted(ENERGY_METRICS))}")
    df["monitor_time"] = pd.to_datetime(df["monitor_time"])
    if df.empty:
        raise ValueError("无数据行")
    return df


def _parse_api_response(resp: httpx.Response) -> pd.DataFrame:
    raw = resp.content
    ctype = (resp.headers.get("content-type") or "").lower()
    if "csv" in ctype or raw.lstrip().startswith(b"building_id"):
        return pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")

    data = resp.json()
    if isinstance(data, list):
        return pd.DataFrame(data)
    if isinstance(data, dict):
        for key in ("items", "records", "data", "rows"):
            chunk = data.get(key)
            if isinstance(chunk, list):
                return pd.DataFrame(chunk)
    raise ValueError("无法解析 API 响应，需 JSON 数组或 {items|records|data} 字段，或 CSV")


def _load_existing_energy() -> pd.DataFrame:
    path = energy_csv_path()
    if not path.is_file():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        return df
    if "monitor_time" in df.columns:
        df["monitor_time"] = pd.to_datetime(df["monitor_time"])
    return df


def _row_keys(df: pd.DataFrame) -> set[tuple[str, str]]:
    if df.empty:
        return set()
    times = df["monitor_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return set(zip(df["building_id"].astype(str), times.astype(str)))


def _merge_and_persist(incoming: pd.DataFrame) -> dict[str, int]:
    existing = _load_existing_energy()
    before_keys = _row_keys(existing)
    incoming_keys = _row_keys(incoming)
    rows_added = len(incoming_keys - before_keys)
    rows_updated = len(incoming_keys & before_keys)

    if existing.empty:
        combined = incoming.copy()
    else:
        combined = pd.concat([existing, incoming], ignore_index=True)
        combined = combined.drop_duplicates(subset=["building_id", "monitor_time"], keep="last")
    combined = combined.sort_values("monitor_time")

    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = IMPORT_DIR / "building_energy_hourly.csv"
    combined.to_csv(out_path, index=False, encoding="utf-8-sig")
    clear_data_caches()

    return {
        "rows_incoming": int(len(incoming)),
        "rows_added": int(rows_added),
        "rows_updated": int(rows_updated),
        "rows_total": int(len(combined)),
    }


def _fetch_remote() -> pd.DataFrame:
    url = settings.energy_api_url
    if not url:
        raise RuntimeError("未配置 ENERGY_API_URL")

    headers: dict[str, str] = {"Accept": "application/json, text/csv"}
    key = settings.energy_api_key
    if key:
        headers["Authorization"] = f"Bearer {key}"

    timeout = settings.energy_api_timeout_sec
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return _normalize_energy_df(_parse_api_response(resp))


def sync_once() -> dict[str, Any]:
    """执行一次拉取合并；供后台任务与手动触发调用。"""
    if not settings.energy_api_url:
        raise RuntimeError("未配置 ENERGY_API_URL")

    if not _sync_lock.acquire(blocking=False):
        raise RuntimeError("同步正在进行中")

    _set_state(running=True, last_sync_at=_now_iso())
    try:
        incoming = _fetch_remote()
        stats = _merge_and_persist(incoming)
        # 触发一次加载以校验
        total = int(len(load_energy()))
        now = _now_iso()
        with _lock:
            _state["running"] = False
            _state["last_success_at"] = now
            _state["last_error"] = None
            _state["consecutive_failures"] = 0
            _state["last_rows_incoming"] = stats["rows_incoming"]
            _state["last_rows_added"] = stats["rows_added"]
            _state["last_rows_updated"] = stats["rows_updated"]
            _state["last_rows_total"] = total
            _state["sync_count"] = int(_state.get("sync_count", 0)) + 1
            _state["success_count"] = int(_state.get("success_count", 0)) + 1
        logger.info(
            "energy sync ok: incoming=%s added=%s total=%s",
            stats["rows_incoming"],
            stats["rows_added"],
            total,
        )
        return {"ok": True, "synced_at": now, **stats, "rows_total": total}
    except Exception as e:
        err = str(e)
        with _lock:
            _state["running"] = False
            _state["last_error"] = err
            _state["consecutive_failures"] = int(_state.get("consecutive_failures", 0)) + 1
            _state["sync_count"] = int(_state.get("sync_count", 0)) + 1
        logger.warning("energy sync failed: %s", err)
        raise
    finally:
        _sync_lock.release()


async def _background_loop() -> None:
    interval = max(30, int(settings.energy_sync_interval_sec))
    while True:
        if settings.energy_api_url:
            try:
                await asyncio.to_thread(sync_once)
            except Exception:
                pass
        await asyncio.sleep(interval)


async def start_sync_loop() -> None:
    """应用启动时注册后台同步（仅当配置了 ENERGY_API_URL）。"""
    global _loop_task
    enabled = bool(settings.energy_api_url)
    _set_state(enabled=enabled)
    if not enabled:
        return

    if settings.energy_sync_on_start:
        try:
            await asyncio.to_thread(sync_once)
        except Exception:
            logger.info("startup energy sync failed; will retry on interval")

    _loop_task = asyncio.create_task(_background_loop())
    logger.info("energy sync loop started (interval=%ss)", settings.energy_sync_interval_sec)


async def stop_sync_loop() -> None:
    global _loop_task
    if _loop_task:
        _loop_task.cancel()
        try:
            await _loop_task
        except asyncio.CancelledError:
            pass
        _loop_task = None
