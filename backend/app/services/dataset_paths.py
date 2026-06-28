"""
HTTP 上传的数据集优先于环境变量路径：backend/data/imported/*.csv
"""
from __future__ import annotations

from pathlib import Path

from app.config import settings

_BACKEND = Path(__file__).resolve().parents[1]
IMPORT_DIR = _BACKEND / "data" / "imported"


def energy_csv_path() -> Path:
    p = IMPORT_DIR / "building_energy_hourly.csv"
    if p.is_file():
        return p
    return settings.energy_csv


def metadata_csv_path() -> Path:
    p = IMPORT_DIR / "metadata_subset.csv"
    if p.is_file():
        return p
    return settings.metadata_csv


def data_dictionary_csv_path() -> Path:
    p = IMPORT_DIR / "data_dictionary.csv"
    if p.is_file():
        return p
    return settings.data_dictionary_csv
