from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps.auth import get_current_user
from app.services import dispatch_recommendation, incidents_store, technicians_store, workorder_flow

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _role(user: dict[str, Any] | None) -> str:
    if not user:
        return "admin"
    return str(user.get("role") or "admin")


def _username(user: dict[str, Any] | None) -> str:
    if not user:
        return "系统"
    return str(user.get("display_name") or user.get("username") or "用户")


@router.get("/summary")
def incidents_summary() -> dict[str, Any]:
    return incidents_store.incident_summary()


@router.get("/technicians")
def list_technicians() -> dict[str, Any]:
    items = technicians_store.list_technicians()
    return {"count": len(items), "items": items}


@router.get("/recommend")
def recommend_technicians(
    building_id: str | None = Query(None),
    location: str | None = Query(None),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    top: int = Query(3, ge=1, le=10),
) -> dict[str, Any]:
    return dispatch_recommendation.recommend_technicians(
        location=location or building_id or "",
        building_id=building_id,
        category=category,
        priority=priority,
        top=top,
    )


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=2)
    building_id: str | None = None
    severity: str = Field("medium", pattern="^(low|medium|high|critical)$")
    status: str = Field("open", pattern="^(open|in_progress|resolved|closed|NEW|DISPATCHED|ACCEPTED|IN_PROGRESS|ON_HOLD|PENDING_CONFIRMATION|COMPLETED|REJECTED|CANCELLED)$")
    source: str = Field("manual", pattern="^(manual|stats|ops|vision)$")
    detail: str | None = None
    requester: str | None = None
    category: str | None = None
    priority: str | None = None
    location: str | None = None
    wo_status: str | None = None


class IncidentPatch(BaseModel):
    title: str | None = None
    building_id: str | None = None
    severity: str | None = Field(None, pattern="^(low|medium|high|critical)$")
    status: str | None = None
    source: str | None = Field(None, pattern="^(manual|stats|ops|vision)$")
    detail: str | None = None


class FlowBody(BaseModel):
    action: str = Field(..., min_length=2)
    technician_id: int | None = None
    remark: str | None = None
    hold_reason: str | None = None
    reject_reason: str | None = None


@router.get("")
def list_incidents(
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    items = incidents_store.list_incidents(status=status, limit=limit)
    return {"count": len(items), "items": items}


@router.post("")
def create_incident(
    body: IncidentCreate,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    item = incidents_store.create_incident(
        title=body.title,
        building_id=body.building_id,
        severity=body.severity,
        status=body.status,
        detail=body.detail,
        source=body.source,
        requester=body.requester or str(user.get("username") or ""),
        category=body.category,
        priority=body.priority,
        location=body.location,
        wo_status=body.wo_status,
    )
    return {"item": item}


@router.get("/{incident_id}")
def get_incident(incident_id: int) -> dict[str, Any]:
    item = incidents_store.get_incident(incident_id)
    if not item:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"item": item}


@router.get("/{incident_id}/history")
def get_incident_history(incident_id: int) -> dict[str, Any]:
    if not incidents_store.get_incident(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found")
    items = incidents_store.list_history(incident_id)
    return {"count": len(items), "items": items}


@router.get("/{incident_id}/recommend")
def recommend_for_incident(incident_id: int, top: int = Query(3, ge=1, le=10)) -> dict[str, Any]:
    try:
        return workorder_flow.recommend_for_incident(incident_id, top=top)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{incident_id}/flow")
def incident_flow(
    incident_id: int,
    body: FlowBody,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    role = _role(user)
    try:
        item = workorder_flow.apply_flow_action(
            incident_id,
            body.action,
            role,  # type: ignore[arg-type]
            operator=_username(user),
            technician_id=body.technician_id,
            remark=body.remark,
            hold_reason=body.hold_reason,
            reject_reason=body.reject_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"item": item}


@router.patch("/{incident_id}")
def patch_incident(incident_id: int, body: IncidentPatch) -> dict[str, Any]:
    item = incidents_store.update_incident(
        incident_id=incident_id,
        title=body.title,
        building_id=body.building_id,
        severity=body.severity,
        status=body.status,
        detail=body.detail,
        source=body.source,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"item": item}


@router.delete("/{incident_id}")
def delete_incident(incident_id: int) -> dict[str, Any]:
    if not incidents_store.delete_incident(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"ok": True, "incident_id": incident_id}
