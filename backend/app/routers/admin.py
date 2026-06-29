from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.services import kb_search, sikong_qa
from app.services.dataset_paths import IMPORT_DIR
from app.services.dataset_upload import (
    validate_and_save_dictionary,
    validate_and_save_energy,
    validate_and_save_metadata,
)
from app.services.energy_store import clear_data_caches, load_energy, load_metadata
from app.services.llm_openai_compat import llm_configured
from app.services.ops_context import clear_dictionary_cache

router = APIRouter(prefix="/admin", tags=["admin"])


def _file_state(p) -> dict[str, Any]:
    try:
        return {"path": str(p), "exists": p.is_file(), "bytes": p.stat().st_size if p.is_file() else 0}
    except Exception as e:
        return {"path": str(p), "exists": False, "error": str(e)}


def _dir_state(p) -> dict[str, Any]:
    try:
        return {"path": str(p), "exists": p.is_dir(), "files": len(list(p.glob("*"))) if p.is_dir() else 0}
    except Exception as e:
        return {"path": str(p), "exists": False, "error": str(e)}


@router.get("/status")
def status() -> dict[str, Any]:
    """数据层状态：路径、就绪性、行数等（便于联调与答辩展示）。"""
    energy_rows = None
    meta_rows = None
    try:
        energy_rows = int(len(load_energy()))
    except Exception:
        pass
    try:
        meta_rows = int(len(load_metadata()))
    except Exception:
        pass

    return {
        "paths": {
            "energy_csv": _file_state(settings.energy_csv),
            "metadata_csv": _file_state(settings.metadata_csv),
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
        "notes": [
            "此路由用于比赛演示与联调，展示数据是否就绪；不涉及鉴权（生产环境请加固）。",
            "知识库索引需先运行 ingest_kb 或调用 POST /api/admin/kb/reindex。",
        ],
    }


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

