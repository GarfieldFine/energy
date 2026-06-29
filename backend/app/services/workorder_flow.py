"""工单流转与历史（融合课设报单系统 ITSM 流程）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services import dispatch_recommendation, technicians_store, workorder_state_machine as sm
from app.services.incidents_store import (
    _connect,
    _gen_order_no,
    _normalize_row,
    add_history,
    get_incident,
    list_history,
    update_incident_fields,
)

EmsRole = sm.EmsRole

_SOURCE_CATEGORY = {
    "stats": "HVAC",
    "vision": "ELECTRIC",
    "ops": "HVAC",
    "manual": "OTHER",
}

_SOURCE_PRIORITY = {
    "stats": "HIGH",
    "vision": "MEDIUM",
    "ops": "MEDIUM",
    "manual": "MEDIUM",
}


def _operator_label(role: EmsRole, username: str = "") -> tuple[str, str]:
    role_map = {
        "admin": "管理员",
        "energy": "能源经理",
        "ops": "运维工程师",
        "requester": "报修员",
    }
    name = username or role_map.get(role, role)
    return name, role_map.get(role, role)


def apply_flow_action(
    incident_id: int,
    action: str,
    role: EmsRole,
    operator: str = "",
    operator_username: str | None = None,
    technician_id: int | None = None,
    remark: str | None = None,
    hold_reason: str | None = None,
    reject_reason: str | None = None,
) -> dict[str, Any]:
    row = get_incident(incident_id)
    if not row:
        raise ValueError("工单不存在")

    from_status = sm.normalize_wo_status(row.get("wo_status"), row.get("status"))
    action = action.strip().lower()
    op_name, op_role = _operator_label(role, operator)

    to_status = from_status
    extra: dict[str, Any] = {}
    old_tech_id = row.get("technician_id")

    if action == "accept":
        to_status = sm.WO_ACCEPTED
        if not technician_id:
            techs = technicians_store.list_technicians()
            technician_id = techs[0]["id"] if techs else None
        if technician_id:
            tech = technicians_store.get_technician(int(technician_id))
            if not tech:
                raise ValueError("维修员不存在")
            extra["technician_id"] = tech["id"]
            extra["technician_name"] = tech["name"]
            technicians_store.adjust_load(int(tech["id"]), 1)
            if old_tech_id and int(old_tech_id) != int(tech["id"]):
                technicians_store.adjust_load(int(old_tech_id), -1)
        sm.validate_transition(from_status, to_status, role)

    elif action == "start":
        to_status = sm.WO_IN_PROGRESS
        sm.validate_transition(from_status, to_status, role)

    elif action == "resume":
        to_status = sm.WO_IN_PROGRESS
        sm.validate_transition(from_status, to_status, role)
        extra["hold_reason"] = None

    elif action == "hold":
        to_status = sm.WO_ON_HOLD
        if not (hold_reason or remark):
            raise ValueError("挂起需填写原因")
        extra["hold_reason"] = hold_reason or remark
        sm.validate_transition(from_status, to_status, role)

    elif action == "submit":
        to_status = sm.WO_PENDING
        sm.validate_transition(from_status, to_status, role)

    elif action == "confirm":
        to_status = sm.WO_COMPLETED
        sm.validate_transition(from_status, to_status, role)
        if row.get("technician_id"):
            technicians_store.adjust_load(int(row["technician_id"]), -1)

    elif action == "reopen":
        to_status = sm.WO_IN_PROGRESS
        sm.validate_transition(from_status, to_status, role)

    elif action == "cancel":
        to_status = sm.WO_CANCELLED
        sm.validate_transition(from_status, to_status, role)
        if row.get("technician_id") and from_status in {
            sm.WO_ACCEPTED,
            sm.WO_IN_PROGRESS,
            sm.WO_ON_HOLD,
        }:
            technicians_store.adjust_load(int(row["technician_id"]), -1)

    elif action == "reject":
        to_status = sm.WO_REJECTED
        extra["reject_reason"] = reject_reason or remark or "OTHER"
        sm.validate_transition(from_status, to_status, role)
        if row.get("technician_id"):
            technicians_store.adjust_load(int(row["technician_id"]), -1)
            extra["technician_id"] = None
            extra["technician_name"] = None

    elif action == "return_pool":
        to_status = sm.WO_NEW
        sm.validate_transition(from_status, to_status, "admin")
        if row.get("technician_id"):
            technicians_store.adjust_load(int(row["technician_id"]), -1)
        extra["technician_id"] = None
        extra["technician_name"] = None
        extra["reject_reason"] = None
        extra["hold_reason"] = None

    elif action == "invite":
        if role not in {"requester", "energy"}:
            raise ValueError("仅报修员可邀请师傅")
        if from_status != sm.WO_NEW or row.get("technician_id"):
            raise ValueError("仅待接单状态可邀请师傅")
        if not technician_id:
            raise ValueError("请选择要邀请的维修师傅")
        tech = technicians_store.get_technician(int(technician_id))
        if not tech or not tech.get("active", 1):
            raise ValueError("维修师傅不存在或已停用")
        if not tech.get("username"):
            raise ValueError("该维修师傅未关联登录账号")
        req_user = operator_username or operator
        if role == "requester" and (row.get("requester") or "") != req_user:
            raise ValueError("只能邀请自己提交的报修单")
        extra["invited_technician_id"] = tech["id"]
        to_status = from_status
        updated = update_incident_fields(incident_id, **extra)
        if not updated:
            raise ValueError("更新失败")
        add_history(
            incident_id,
            from_status,
            from_status,
            op_name,
            op_role,
            f"邀请 {tech['name']} 接单",
        )
        return _normalize_row(updated)

    elif action == "reassign":
        to_status = sm.WO_DISPATCHED
        if not technician_id:
            raise ValueError("转派需指定维修员")
        tech = technicians_store.get_technician(int(technician_id))
        if not tech:
            raise ValueError("维修员不存在")
        if old_tech_id and int(old_tech_id) != int(tech["id"]):
            technicians_store.adjust_load(int(old_tech_id), -1)
        extra["technician_id"] = tech["id"]
        extra["technician_name"] = tech["name"]
        extra["invited_technician_id"] = tech["id"]
        sm.validate_transition(from_status, to_status, "admin")

    elif action == "dispatch_accept":
        to_status = sm.WO_ACCEPTED
        sm.validate_transition(from_status, to_status, role)
        if row.get("technician_id"):
            technicians_store.adjust_load(int(row["technician_id"]), 1)

    elif action == "submit_draft":
        if from_status != sm.WO_VISION_DRAFT:
            raise ValueError("仅视觉预警草稿可提交报修")
        to_status = sm.WO_NEW
        sm.validate_transition(from_status, to_status, role)

    else:
        raise ValueError(f"未知操作：{action}")

    extra["wo_status"] = to_status
    extra["status"] = sm.WO_TO_LEGACY.get(to_status, "open")
    updated = update_incident_fields(incident_id, **extra)
    if not updated:
        raise ValueError("更新失败")

    hist_remark = remark or hold_reason or reject_reason or action
    add_history(
        incident_id,
        from_status,
        to_status,
        op_name,
        op_role,
        hist_remark,
    )
    return _normalize_row(updated)


def recommend_for_incident(incident_id: int, top: int = 3) -> dict[str, Any]:
    row = get_incident(incident_id)
    if not row:
        raise ValueError("工单不存在")
    loc = row.get("location") or row.get("building_id") or ""
    return dispatch_recommendation.recommend_technicians(
        location=str(loc),
        building_id=row.get("building_id"),
        category=row.get("category"),
        priority=row.get("priority"),
        top=top,
    )
