"""ITSM 工单状态机（融合软件设计课设 WorkOrderStateMachine）。"""
from __future__ import annotations

from typing import Literal

EmsRole = Literal["admin", "energy", "ops", "requester"]

WO_NEW = "NEW"
WO_DISPATCHED = "DISPATCHED"
WO_ACCEPTED = "ACCEPTED"
WO_IN_PROGRESS = "IN_PROGRESS"
WO_ON_HOLD = "ON_HOLD"
WO_PENDING = "PENDING_CONFIRMATION"
WO_COMPLETED = "COMPLETED"
WO_REJECTED = "REJECTED"
WO_CANCELLED = "CANCELLED"
WO_VISION_DRAFT = "VISION_DRAFT"

LEGACY_TO_WO = {
    "open": WO_NEW,
    "in_progress": WO_IN_PROGRESS,
    "resolved": WO_PENDING,
    "closed": WO_COMPLETED,
}

WO_TO_LEGACY = {
    WO_NEW: "open",
    WO_DISPATCHED: "open",
    WO_ACCEPTED: "in_progress",
    WO_IN_PROGRESS: "in_progress",
    WO_ON_HOLD: "in_progress",
    WO_PENDING: "resolved",
    WO_COMPLETED: "closed",
    WO_REJECTED: "open",
    WO_CANCELLED: "closed",
    WO_VISION_DRAFT: "open",
}


def normalize_wo_status(raw: str | None, legacy_status: str | None = None) -> str:
    if raw and raw in _ALL_WO:
        return raw
    if legacy_status:
        return LEGACY_TO_WO.get(legacy_status, WO_NEW)
    return WO_NEW


_ALL_WO = {
    WO_NEW,
    WO_DISPATCHED,
    WO_ACCEPTED,
    WO_IN_PROGRESS,
    WO_ON_HOLD,
    WO_PENDING,
    WO_COMPLETED,
    WO_REJECTED,
    WO_CANCELLED,
    WO_VISION_DRAFT,
}


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status == to_status:
        return True
    f, t = from_status, to_status
    if f == WO_VISION_DRAFT:
        return t in {WO_NEW, WO_CANCELLED}
    if f == WO_NEW:
        return t in {WO_ACCEPTED, WO_CANCELLED}
    if f == WO_DISPATCHED:
        return t in {WO_ACCEPTED, WO_REJECTED, WO_CANCELLED}
    if f == WO_ACCEPTED:
        return t in {WO_IN_PROGRESS, WO_ON_HOLD, WO_REJECTED, WO_CANCELLED}
    if f == WO_IN_PROGRESS:
        return t in {WO_ON_HOLD, WO_PENDING, WO_COMPLETED, WO_REJECTED, WO_CANCELLED}
    if f == WO_ON_HOLD:
        return t in {WO_IN_PROGRESS, WO_REJECTED, WO_CANCELLED}
    if f == WO_PENDING:
        return t in {WO_COMPLETED, WO_IN_PROGRESS, WO_CANCELLED}
    if f == WO_REJECTED:
        return t in {WO_NEW, WO_CANCELLED}
    return False


def role_may_transition(from_status: str, to_status: str, role: EmsRole) -> bool:
    if role == "admin":
        return True
    if from_status == WO_VISION_DRAFT:
        if to_status == WO_CANCELLED:
            return role in {"admin", "requester", "energy", "ops"}
        if to_status == WO_NEW:
            return role in {"admin", "requester", "energy", "ops"}
    if role == "requester":
        if to_status == WO_CANCELLED:
            return from_status in {WO_NEW, WO_DISPATCHED, WO_ACCEPTED}
        return from_status == WO_PENDING and to_status in {WO_COMPLETED, WO_IN_PROGRESS}
    if role == "energy":
        if to_status == WO_CANCELLED:
            return from_status in {WO_NEW, WO_DISPATCHED, WO_ACCEPTED}
        return from_status == WO_PENDING and to_status in {WO_COMPLETED, WO_IN_PROGRESS}
    if role == "ops":
        if to_status == WO_ACCEPTED:
            return from_status in {WO_NEW, WO_DISPATCHED}
        if to_status == WO_IN_PROGRESS:
            return from_status in {WO_ACCEPTED, WO_ON_HOLD}
        if to_status == WO_ON_HOLD:
            return from_status in {WO_ACCEPTED, WO_IN_PROGRESS}
        if to_status == WO_PENDING:
            return from_status == WO_IN_PROGRESS
        if to_status == WO_REJECTED:
            return from_status in {WO_DISPATCHED, WO_ACCEPTED, WO_IN_PROGRESS, WO_ON_HOLD}
    return False


def validate_transition(from_status: str, to_status: str, role: EmsRole) -> None:
    if not can_transition(from_status, to_status):
        raise ValueError(f"非法状态流转：{from_status} → {to_status}")
    if not role_may_transition(from_status, to_status, role):
        raise ValueError("当前角色无权执行该状态变更")
