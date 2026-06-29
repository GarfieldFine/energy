"""工单 API 响应：与课设 Spring Boot 字段命名（camelCase）对齐。"""
from __future__ import annotations

from typing import Any


def to_api_order(row: dict[str, Any]) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "id": row.get("id"),
        "orderNo": row.get("order_no"),
        "title": row.get("title"),
        "description": row.get("description") or row.get("detail") or "",
        "location": row.get("location") or row.get("building_id") or "",
        "province": row.get("province"),
        "city": row.get("city"),
        "district": row.get("district"),
        "addressDetail": row.get("address_detail"),
        "campus": row.get("campus"),
        "building": row.get("building") or row.get("building_id"),
        "floor": row.get("floor"),
        "room": row.get("room"),
        "category": row.get("category") or "OTHER",
        "priority": row.get("priority") or "MEDIUM",
        "expectedCompletionType": row.get("expected_completion_type") or "ASAP",
        "expectedCompletionAt": row.get("expected_completion_at"),
        "attachmentFilename": row.get("attachment_filename"),
        "requester": row.get("requester") or "",
        "contactPhone": row.get("contact_phone"),
        "status": row.get("wo_status") or row.get("status"),
        "technicianId": row.get("technician_id"),
        "technicianName": row.get("technician_name"),
        "invitedTechnicianId": row.get("invited_technician_id"),
        "severity": row.get("severity"),
        "source": row.get("source"),
        "holdReason": row.get("hold_reason"),
        "rejectReason": row.get("reject_reason"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def to_api_history(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "workOrderId": row.get("incident_id"),
        "fromStatus": row.get("from_status"),
        "toStatus": row.get("to_status"),
        "operatorName": row.get("operator_name"),
        "operatorRole": row.get("operator_role"),
        "remark": row.get("remark"),
        "createdAt": row.get("created_at"),
    }


def to_api_technician(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "region": row.get("region"),
        "skillLevel": row.get("skill_level"),
        "contactPhone": row.get("contact_phone"),
        "active": bool(row.get("active", 1)),
        "loadCount": row.get("load_count"),
        "username": row.get("username"),
    }
