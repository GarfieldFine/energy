"""
能耗 / 元数据 / 数据字典 CSV 上传校验与落盘。
"""
from __future__ import annotations

import io
from typing import Any

import pandas as pd

from app.services.dataset_paths import IMPORT_DIR

ENERGY_REQUIRED = {"building_id", "monitor_time"}
ENERGY_METRICS = {
    "electricity_kwh",
    "solar_kwh",
    "chilledwater_kwh_eq",
    "hotwater_kwh",
    "water_m3",
    "air_temperature_c",
    "relative_humidity_pct",
}


def _read_csv_bytes(raw: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")


def validate_and_save_energy(raw: bytes) -> dict[str, Any]:
    df = _read_csv_bytes(raw)
    cols = {str(c).strip() for c in df.columns}
    missing = ENERGY_REQUIRED - cols
    if missing:
        raise ValueError(f"缺少必填列：{', '.join(sorted(missing))}")
    if not ENERGY_METRICS & cols:
        raise ValueError(f"至少需包含一类能耗/环境指标列之一：{', '.join(sorted(ENERGY_METRICS))}")
    try:
        df["monitor_time"] = pd.to_datetime(df["monitor_time"])
    except Exception as e:
        raise ValueError(f"monitor_time 列无法解析为时间：{e}") from e
    if df.empty:
        raise ValueError("CSV 无数据行")
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = IMPORT_DIR / "building_energy_hourly.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return {"ok": True, "path": str(path), "rows": int(len(df)), "columns": list(df.columns)}


def validate_and_save_metadata(raw: bytes) -> dict[str, Any]:
    df = _read_csv_bytes(raw)
    cols = {str(c).strip() for c in df.columns}
    if "building_id" not in cols:
        raise ValueError("元数据 CSV 须包含 building_id 列")
    if df.empty:
        raise ValueError("CSV 无数据行")
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = IMPORT_DIR / "metadata_subset.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return {"ok": True, "path": str(path), "rows": int(len(df)), "columns": list(df.columns)}


def validate_and_save_dictionary(raw: bytes) -> dict[str, Any]:
    df = _read_csv_bytes(raw)
    if df.shape[1] < 1:
        raise ValueError("数据字典至少需一列")
    if df.empty:
        raise ValueError("CSV 无数据行")
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = IMPORT_DIR / "data_dictionary.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return {"ok": True, "path": str(path), "rows": int(len(df)), "columns": list(df.columns)}
