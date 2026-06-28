from __future__ import annotations

import csv
from typing import Any

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/data-dictionary")
def data_dictionary() -> dict[str, Any]:
    rows = []
    with open(settings.data_dictionary_csv, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(dict(r))
    return {"items": rows}
