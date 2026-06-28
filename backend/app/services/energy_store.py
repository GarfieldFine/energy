from __future__ import annotations

import functools
from datetime import datetime
from typing import Any

import pandas as pd

from app.config import settings
from app.services.dataset_paths import energy_csv_path, metadata_csv_path


@functools.lru_cache(maxsize=1)
def load_energy() -> pd.DataFrame:
    df = pd.read_csv(energy_csv_path(), encoding="utf-8-sig")
    df["monitor_time"] = pd.to_datetime(df["monitor_time"])
    return df


@functools.lru_cache(maxsize=1)
def load_metadata() -> pd.DataFrame:
    return pd.read_csv(metadata_csv_path(), encoding="utf-8-sig")


def clear_data_caches() -> None:
    load_energy.cache_clear()
    load_metadata.cache_clear()


def query_energy(
    building_id: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    df = load_energy()
    if building_id:
        df = df[df["building_id"] == building_id]
    if time_from:
        df = df[df["monitor_time"] >= pd.to_datetime(time_from)]
    if time_to:
        df = df[df["monitor_time"] <= pd.to_datetime(time_to)]
    df = df.sort_values("monitor_time")
    if limit > 0:
        df = df.head(limit)
    out = df.copy()
    out["monitor_time"] = out["monitor_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out.fillna("").to_dict(orient="records")


def list_buildings() -> list[dict[str, Any]]:
    meta = load_metadata()
    return meta.fillna("").to_dict(orient="records")
