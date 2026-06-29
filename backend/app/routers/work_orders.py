"""
课设报单系统 REST 兼容层：路径与 GarfieldFine 课设 WorkOrderController 一致。
底层仍使用 incidents_store + workorder_flow。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps.auth import get_current_user
from app.services import dispatch_recommendation, incidents_store, technicians_store, workorder_flow
from app.services.workorder_mapper import to_api_history, to_api_order, to_api_technician
from app.services import workorder_state_machine as sm

router = APIRouter(prefix="/work-orders", tags=["work-orders-compat"])


def _wo_role(user: dict[str, Any]) -> str:
    r = str(user.get("role") or "admin")
    return {"admin": "ADMIN", "ops": "TECHNICIAN", "requester": "REQUESTER", "energy": "REQUESTER"}.get(r, r.upper())


def _can_see_order(row: dict[str, Any], user: dict[str, Any]) -> bool:
    role = user.get("role")
    if role in {"admin", "energy"}:
        return True
    if role == "requester":
        return (row.get("requester") or "") == user.get("username")
    if role == "ops":
        wo = sm.normalize_wo_status(row.get("wo_status"), row.get("status"))
        if wo in {sm.WO_NEW, sm.WO_DISPATCHED, sm.WO_VISION_DRAFT}:
            return True
        tid = row.get("technician_id")
        return tid is not None
    return False


class WorkOrderRequest(BaseModel):
    title: str
    description: str = ""
    province: str | None = None
    city: str | None = None
    district: str | None = None
    addressDetail: str | None = None
    campus: str | None = None
    building: str | None = None
    floor: str | None = None
    room: str | None = None
    category: str = "OTHER"
    priority: str = "MEDIUM"
    expectedCompletionType: str = "ASAP"
    expectedCompletionAt: str | None = None
    attachmentFilename: str | None = None
    requester: str | None = None
    contactPhone: str | None = None
    location: str | None = None


class HoldBody(BaseModel):
    reason: str = Field(..., min_length=1)


class RejectBody(BaseModel):
    reason: str = Field(..., min_length=1)
    remark: str | None = None


class InviteBody(BaseModel):
    technicianId: int


class ReassignBody(BaseModel):
    technicianId: int


class StatusBody(BaseModel):
    remark: str | None = None


class DraftPatchBody(BaseModel):
    title: str | None = None
    description: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    addressDetail: str | None = None
    campus: str | None = None
    building: str | None = None
    floor: str | None = None
    room: str | None = None
    location: str | None = None
    contactPhone: str | None = None
    category: str | None = None
    priority: str | None = None


def _is_order_owner(row: dict[str, Any], user: dict[str, Any]) -> bool:
    return (row.get("requester") or "") == user.get("username")


def _can_edit_order(row: dict[str, Any], user: dict[str, Any]) -> bool:
    role = user.get("role")
    wo = sm.normalize_wo_status(row.get("wo_status"), row.get("status"))
    if role == "admin":
        return True
    if not _is_order_owner(row, user):
        return False
    if wo == sm.WO_VISION_DRAFT:
        return role in {"requester", "ops"}
    if role == "requester" and wo in {sm.WO_NEW, sm.WO_DISPATCHED} and not row.get("technician_id"):
        return True
    return False


def _can_delete_vision_draft(row: dict[str, Any], user: dict[str, Any]) -> bool:
    wo = sm.normalize_wo_status(row.get("wo_status"), row.get("status"))
    if wo != sm.WO_VISION_DRAFT:
        return False
    role = user.get("role")
    if role == "admin":
        return True
    if role in {"requester", "ops"}:
        return _is_order_owner(row, user)
    return False


def _apply_patch_fields(body: DraftPatchBody) -> dict[str, Any]:
    loc = body.location
    if loc is None:
        loc = incidents_store.compose_location(
            body.province,
            body.city,
            body.district,
            body.addressDetail,
            body.building,
            body.floor,
            body.room,
            body.campus,
        ) or None
    fields: dict[str, Any] = {}
    if body.title is not None:
        fields["title"] = body.title
    if body.description is not None:
        fields["description"] = body.description
        fields["detail"] = body.description
    if body.province is not None:
        fields["province"] = body.province
    if body.city is not None:
        fields["city"] = body.city
    if body.district is not None:
        fields["district"] = body.district
    if body.addressDetail is not None:
        fields["address_detail"] = body.addressDetail
    if body.campus is not None:
        fields["campus"] = body.campus
    if body.building is not None:
        fields["building_id"] = body.building
    if body.floor is not None:
        fields["floor"] = body.floor
    if body.room is not None:
        fields["room"] = body.room
    if loc is not None:
        fields["location"] = loc
    if body.contactPhone is not None:
        fields["contact_phone"] = body.contactPhone
    if body.category is not None:
        fields["category"] = body.category
    if body.priority is not None:
        fields["priority"] = body.priority
    return fields


@router.get("/recommend")
def recommend(
    location: str = Query(...),
    mode: str = Query("chain"),
    campus: str | None = Query(None),
    building: str | None = Query(None),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    top: int = Query(3, ge=1, le=10),
) -> dict[str, Any]:
    data = dispatch_recommendation.recommend_technicians(
        location=location,
        building_id=building,
        category=category,
        priority=priority,
        top=top,
        mode=mode,
    )
    items = []
    for it in data.get("items") or []:
        items.append(
            {
                "id": it["id"],
                "name": it["name"],
                "region": it["region"],
                "skillLevel": it.get("skill_level"),
                "loadCount": it.get("load_count"),
                "matchScore": it.get("match_score"),
                "matchReasons": it.get("match_reasons") or [],
                "rank": it.get("rank"),
            }
        )
    first = items[0] if items else None
    summary = data.get("summary") or ""
    return {
        "mode": data.get("mode"),
        "modeLabel": data.get("mode_label"),
        "summary": summary,
        "reason": summary,
        "topRecommendations": items,
        "items": items,
        "id": first["id"] if first else None,
        "name": first["name"] if first else None,
        "region": first["region"] if first else None,
        "loadCount": first["loadCount"] if first else None,
    }


@router.get("")
def list_orders(
    status: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    rows = incidents_store.list_incidents_for_user(user.get("role"), user.get("username"), status=status)
    return [to_api_order(r) for r in rows if _can_see_order(r, user)]


@router.get("/available")
def available_orders(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    if user.get("role") != "ops":
        raise HTTPException(status_code=403, detail="仅维修员可查看待接单池")
    rows = incidents_store.list_incidents(status=sm.WO_NEW, limit=200)
    rows += incidents_store.list_incidents(status=sm.WO_DISPATCHED, limit=200)
    seen = set()
    out = []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        out.append(to_api_order(r))
    return out


@router.get("/{order_id}/history")
def order_history(order_id: int, user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    row = incidents_store.get_incident(order_id)
    if not row or not _can_see_order(row, user):
        raise HTTPException(status_code=404, detail="工单不存在")
    return [to_api_history(h) for h in incidents_store.list_history(order_id)]


def _can_edit_vision_draft(row: dict[str, Any], user: dict[str, Any]) -> bool:
    wo = sm.normalize_wo_status(row.get("wo_status"), row.get("status"))
    return wo == sm.WO_VISION_DRAFT and _can_edit_order(row, user)


@router.patch("/{order_id}")
def patch_draft_order(
    order_id: int,
    body: DraftPatchBody,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    row = incidents_store.get_incident(order_id)
    if not row or not _can_see_order(row, user):
        raise HTTPException(status_code=404, detail="工单不存在")
    if not _can_edit_order(row, user):
        raise HTTPException(status_code=403, detail="无权编辑该工单")
    fields = _apply_patch_fields(body)
    updated = incidents_store.update_incident_fields(order_id, **fields)
    if not updated:
        raise HTTPException(status_code=404, detail="工单不存在")
    return to_api_order(updated)


@router.post("/{order_id}/submit-draft")
def submit_draft_order(order_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    row = incidents_store.get_incident(order_id)
    if not row or not _can_see_order(row, user):
        raise HTTPException(status_code=404, detail="工单不存在")
    if not _can_edit_vision_draft(row, user):
        raise HTTPException(status_code=403, detail="无权提交该视觉草稿")
    return _flow(order_id, "submit_draft", user, remark="视觉草稿确认提交报修")


@router.post("")
def create_order(body: WorkOrderRequest, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    role = user.get("role")
    if role not in {"admin", "requester"}:
        raise HTTPException(status_code=403, detail="无权限提交报修")
    loc = body.location or incidents_store.compose_location(
        body.province, body.city, body.district, body.addressDetail,
        body.building, body.floor, body.room, body.campus,
    )
    req = body.requester if role == "admin" and body.requester else user.get("username")
    sev = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high", "URGENT": "critical"}.get(body.priority.upper(), "medium")
    row = incidents_store.create_incident(
        title=body.title,
        severity=sev,
        building_id=body.building,
        detail=body.description,
        source="manual",
        requester=req,
        category=body.category,
        priority=body.priority,
        location=loc,
        province=body.province,
        city=body.city,
        district=body.district,
        address_detail=body.addressDetail,
        campus=body.campus,
        floor=body.floor,
        room=body.room,
        contact_phone=body.contactPhone,
        description=body.description,
        expected_completion_type=body.expectedCompletionType,
        expected_completion_at=body.expectedCompletionAt,
        attachment_filename=body.attachmentFilename,
    )
    return to_api_order(row)


def _flow(order_id: int, action: str, user: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    role = user.get("role") or "admin"
    kwargs.setdefault("operator_username", str(user.get("username") or ""))
    try:
        row = workorder_flow.apply_flow_action(
            order_id,
            action,
            role,  # type: ignore[arg-type]
            operator=str(user.get("display_name") or user.get("username") or ""),
            **kwargs,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return to_api_order(row)


@router.post("/{order_id}/accept")
def accept(order_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    tech_id: int | None = None
    if user.get("role") == "ops":
        me = technicians_store.find_by_username(str(user.get("username") or ""))
        tech_id = int(me["id"]) if me else None
    if tech_id is None:
        techs = technicians_store.list_technicians()
        tech_id = int(techs[0]["id"]) if techs else None
    return _flow(order_id, "accept", user, technician_id=tech_id)


@router.post("/{order_id}/start")
def start(order_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _flow(order_id, "start", user)


@router.post("/{order_id}/hold")
def hold(order_id: int, body: HoldBody, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _flow(order_id, "hold", user, hold_reason=body.reason)


@router.post("/{order_id}/resume")
def resume(order_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _flow(order_id, "resume", user)


@router.post("/{order_id}/submit-for-confirmation")
def submit_confirm(order_id: int, user: dict[str, Any] = Depends(get_current_user), body: StatusBody | None = None) -> dict[str, Any]:
    return _flow(order_id, "submit", user, remark=body.remark if body else None)


@router.post("/{order_id}/confirm")
def confirm(order_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _flow(order_id, "confirm", user)


@router.post("/{order_id}/reopen")
def reopen(order_id: int, user: dict[str, Any] = Depends(get_current_user), body: StatusBody | None = None) -> dict[str, Any]:
    return _flow(order_id, "reopen", user, remark=body.remark if body else None)


@router.post("/{order_id}/reject")
def reject(order_id: int, body: RejectBody, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _flow(order_id, "reject", user, reject_reason=body.reason, remark=body.remark)


@router.post("/{order_id}/return-to-pool")
def return_pool(order_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _flow(order_id, "return_pool", user)


@router.post("/{order_id}/invite")
def invite(order_id: int, body: InviteBody, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _flow(order_id, "invite", user, technician_id=body.technicianId)


@router.post("/{order_id}/reassign")
def reassign(order_id: int, body: ReassignBody, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _flow(order_id, "reassign", user, technician_id=body.technicianId)


@router.delete("/{order_id}")
def cancel(order_id: int, user: dict[str, Any] = Depends(get_current_user), reason: str | None = Query(None)) -> dict[str, Any]:
    return _flow(order_id, "cancel", user, remark=reason or "用户取消")


@router.delete("/{order_id}/record")
def delete_record(order_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, str]:
    row = incidents_store.get_incident(order_id)
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")
    role = user.get("role")
    wo = sm.normalize_wo_status(row.get("wo_status"), row.get("status"))
    if role == "admin":
        pass
    elif _can_delete_vision_draft(row, user):
        pass
    else:
        raise HTTPException(status_code=403, detail="无权删除该工单")
    if not incidents_store.delete_incident(order_id):
        raise HTTPException(status_code=500, detail="删除失败")
    return {"message": "已删除"}


technicians_router = APIRouter(prefix="/technicians", tags=["work-orders-compat"])


@technicians_router.get("")
def list_all_technicians() -> list[dict[str, Any]]:
    technicians_store.recalculate_loads_from_incidents()
    return [to_api_technician(t) for t in technicians_store.list_technicians(active_only=False)]
