from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.services import energy_store

router = APIRouter(prefix="/energy", tags=["energy"])


@router.get("/buildings")
def list_buildings() -> dict[str, Any]:
    return {"items": energy_store.list_buildings()}


@router.get("/records")
def query_records(
    building_id: str | None = Query(None),
    time_from: str | None = Query(None, description="含该时刻，如 2016-01-02 17:00:00"),
    time_to: str | None = Query(None),
    limit: int = Query(500, ge=1, le=10000),
) -> dict[str, Any]:
    rows = energy_store.query_energy(
        building_id=building_id,
        time_from=time_from,
        time_to=time_to,
        limit=limit,
    )
    return {"count": len(rows), "items": rows}
