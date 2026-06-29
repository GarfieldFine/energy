from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.services import kb_search, sikong_qa
from app.services.dataset_paths import IMPORT_DIR, energy_csv_path, metadata_csv_path
from app.services.dataset_upload import (
    validate_and_save_dictionary,
    validate_and_save_energy,
    validate_and_save_metadata,
)
from app.services.energy_store import clear_data_caches, load_energy, load_metadata
from app.services.energy_sync import get_sync_state, sync_once
from app.services.llm_openai_compat import llm_configured
from app.services.ops_context import clear_dictionary_cache

router = APIRouter(prefix="/admin", tags=["admin"])


def _file_state(p) -> dict[str, Any]:
    try:
        state: dict[str, Any] = {
            "path": str(p),
            "exists": p.is_file(),
            "bytes": p.stat().st_size if p.is_file() else 0,
        }
        if p.is_file():
            state["modified_at"] = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
        return state
    except Exception as e:
        return {"path": str(p), "exists": False, "error": str(e)}


def _dir_state(p) -> dict[str, Any]:
    try:
        return {"path": str(p), "exists": p.is_dir(), "files": len(list(p.glob("*"))) if p.is_dir() else 0}
    except Exception as e:
        return {"path": str(p), "exists": False, "error": str(e)}


def _energy_time_bounds() -> tuple[str | None, str | None]:
    try:
        df = load_energy()
        if df.empty or "monitor_time" not in df.columns:
            return None, None
        col = df["monitor_time"]
        t_min, t_max = col.min(), col.max()
        return (
            t_min.isoformat() if hasattr(t_min, "isoformat") else str(t_min),
            t_max.isoformat() if hasattr(t_max, "isoformat") else str(t_max),
        )
    except Exception:
        return None, None


def _sync_mode() -> str:
    if settings.energy_api_url:
        return "api"
    if (IMPORT_DIR / "building_energy_hourly.csv").is_file():
        return "import"
    return "file"


def _source_status(*, exists: bool, rows: int | None) -> str:
    if not exists:
        return "missing"
    if rows is None:
        return "unknown"
    if rows <= 0:
        return "empty"
    return "ok"


@router.get("/status")
def status() -> dict[str, Any]:
    """数据层与对接状态：路径、就绪性、行数、同步模式（平台运维页）。"""
    energy_rows = None
    meta_rows = None
    energy_path = energy_csv_path()
    meta_path = metadata_csv_path()
    energy_file = _file_state(energy_path)
    meta_file = _file_state(meta_path)
    try:
        energy_rows = int(len(load_energy()))
    except Exception:
        pass
    try:
        meta_rows = int(len(load_metadata()))
    except Exception:
        pass

    time_min, time_max = _energy_time_bounds()
    mode = _sync_mode()
    checked_at = datetime.now(timezone.utc).isoformat()
    api_sync = get_sync_state()

    energy_last_updated = energy_file.get("modified_at")
    if mode == "api" and api_sync.get("last_success_at"):
        energy_last_updated = api_sync["last_success_at"]

    data_sources: list[dict[str, Any]] = [
        {
            "id": "energy",
            "name": "能耗时序",
            "kind": mode if mode != "file" else "csv",
            "status": _source_status(exists=bool(energy_file.get("exists")), rows=energy_rows),
            "rows": energy_rows,
            "active_path": str(energy_path),
            "last_updated": energy_last_updated,
            "time_min": time_min,
            "time_max": time_max,
        },
        {
            "id": "metadata",
            "name": "建筑元数据",
            "kind": "import" if (IMPORT_DIR / "metadata_subset.csv").is_file() else "csv",
            "status": _source_status(exists=bool(meta_file.get("exists")), rows=meta_rows),
            "rows": meta_rows,
            "active_path": str(meta_path),
            "last_updated": meta_file.get("modified_at"),
        },
        {
            "id": "kb",
            "name": "规范知识库",
            "kind": "index",
            "status": "ok" if kb_search.is_index_ready() else "missing",
            "rows": None,
            "active_path": str(settings.kb_index_db),
            "last_updated": _file_state(settings.kb_index_db).get("modified_at"),
        },
        {
            "id": "sikong",
            "name": "司空语料",
            "kind": "jsonl",
            "status": "ok" if sikong_qa.is_ready() else "missing",
            "rows": sikong_qa.count_rows(),
            "active_path": str(settings.sikong_jsonl),
            "last_updated": _file_state(settings.sikong_jsonl).get("modified_at"),
        },
    ]

    return {
        "paths": {
            "energy_csv": energy_file,
            "metadata_csv": meta_file,
            "data_dictionary_csv": _file_state(settings.data_dictionary_csv),
            "kb_root": _dir_state(settings.kb_root),
            "kb_index_db": _file_state(settings.kb_index_db),
            "sikong_jsonl": _file_state(settings.sikong_jsonl),
        },
        "ready": {
            "kb_index_ready": kb_search.is_index_ready(),
            "sikong_ready": sikong_qa.is_ready(),
            "llm_configured": llm_configured(),
        },
        "llm": {
            "model": settings.llm_model if llm_configured() else None,
            "api_base": settings.llm_api_base if llm_configured() else None,
        },
        "counts": {
            "energy_rows": energy_rows,
            "metadata_rows": meta_rows,
            "sikong_rows": sikong_qa.count_rows(),
        },
        "sync": {
            "mode": mode,
            "checked_at": checked_at,
            "energy_api_url": settings.energy_api_url,
            "sync_interval_sec": settings.energy_sync_interval_sec,
            "energy_time_min": time_min,
            "energy_time_max": time_max,
            **api_sync,
        },
        "data_sources": data_sources,
        "notes": [
            "平台运维页：API 健康、数据源与同步状态。",
            "配置 ENERGY_API_URL 后后台按 ENERGY_SYNC_INTERVAL_SEC 自动拉取并合并能耗数据。",
            "POST /api/admin/energy/sync 可手动触发一次 API 同步。",
            "未配置 API 时：本地 CSV 或 HTTP 离线导入；POST /api/admin/reload 仅刷新内存缓存。",
        ],
    }


@router.post("/energy/sync")
def energy_sync_now() -> dict[str, Any]:
    """手动触发一次能耗 API 同步（需配置 ENERGY_API_URL）。"""
    if not settings.energy_api_url:
        raise HTTPException(status_code=400, detail="未配置 ENERGY_API_URL")
    try:
        return sync_once()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/reload")
def reload_data() -> dict[str, Any]:
    """清理缓存并重新加载（用于切换数据路径或更新 CSV 后）。"""
    load_energy.cache_clear()
    load_metadata.cache_clear()
    sikong_qa._load_rows.cache_clear()  # type: ignore[attr-defined]

    # 再次触发一次加载，便于直接看到计数
    energy_rows = int(len(load_energy()))
    meta_rows = int(len(load_metadata()))
    sik_rows = sikong_qa.count_rows()
    return {
        "reloaded": True,
        "reloaded_at": datetime.now(timezone.utc).isoformat(),
        "counts": {"energy_rows": energy_rows, "metadata_rows": meta_rows, "sikong_rows": sik_rows},
        "paths": {
            "energy_csv": str(settings.energy_csv),
            "metadata_csv": str(settings.metadata_csv),
            "sikong_jsonl": str(settings.sikong_jsonl),
            "kb_index_db": str(settings.kb_index_db),
        },
    }


@router.get("/dataset/import-status")
def dataset_import_status() -> dict[str, Any]:
    """展示 HTTP 上传数据集是否覆盖默认路径。"""
    from app.services.dataset_paths import (
        data_dictionary_csv_path,
        energy_csv_path,
        metadata_csv_path,
    )

    def _info(name: str, resolver) -> dict[str, Any]:
        imp = IMPORT_DIR / name
        return {
            "imported_file_exists": imp.is_file(),
            "active_path": str(resolver()),
            "using_imported": imp.is_file(),
        }

    return {
        "import_dir": str(IMPORT_DIR),
        "energy": _info("building_energy_hourly.csv", energy_csv_path),
        "metadata": _info("metadata_subset.csv", metadata_csv_path),
        "data_dictionary": _info("data_dictionary.csv", data_dictionary_csv_path),
    }


@router.post("/dataset/upload-energy")
async def dataset_upload_energy(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空文件")
    try:
        out = validate_and_save_energy(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    clear_data_caches()
    out["counts"] = {"energy_rows": int(len(load_energy()))}
    return out


@router.post("/dataset/upload-metadata")
async def dataset_upload_metadata(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空文件")
    try:
        out = validate_and_save_metadata(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    clear_data_caches()
    out["counts"] = {
        "energy_rows": int(len(load_energy())),
        "metadata_rows": int(len(load_metadata())),
    }
    return out


@router.post("/dataset/upload-dictionary")
async def dataset_upload_dictionary(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空文件")
    try:
        out = validate_and_save_dictionary(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    clear_dictionary_cache()
    return out


@router.post("/kb/reindex")
def kb_reindex() -> dict[str, Any]:
    """在 API 内触发知识库重建索引（演示/联调用，可能较慢）。"""
    from scripts import ingest_kb  # 本地脚本（backend 目录可 import）

    ingest_kb.main()
    return {"ok": True, "kb_index_db": str(settings.kb_index_db), "index_ready": kb_search.is_index_ready()}
