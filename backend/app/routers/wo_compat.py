"""课设报单系统兼容端点：用户、附件、导出、维修档案申请。"""
from __future__ import annotations

import csv
import io
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.deps.auth import get_current_user
from app.services import amap_service, incidents_store, technician_profile_requests_store, users_store

router = APIRouter(tags=["work-orders-compat"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "attachments"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class UserUpdateBody(BaseModel):
    active: bool | None = None


class ResetPasswordBody(BaseModel):
    password: str | None = None


class ProfileChangeBody(BaseModel):
    region: str = Field(..., min_length=1)
    skillLevel: str = Field(..., min_length=1)
    contactPhone: str = Field(..., min_length=1)
    attachmentFilename: str = Field(..., min_length=1)


class RejectProfileBody(BaseModel):
    reason: str | None = None


@router.get("/users")
def list_users(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看用户列表")
    return users_store.list_users()


@router.put("/users/{user_id}")
def update_user(user_id: int, body: UserUpdateBody, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    try:
        return users_store.update_user(user_id, active=body.active)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    body: ResetPasswordBody | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    try:
        users_store.reset_password(user_id, (body.password if body else None) or "123456")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"message": "密码已重置"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, str]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    try:
        users_store.delete_user(user_id, str(user.get("username") or ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"message": "账号已删除"}


@router.get("/users/roles")
def list_user_roles() -> list[dict[str, str]]:
    return [
        {"id": "ADMIN", "name": "管理员"},
        {"id": "TECHNICIAN", "name": "维修员"},
        {"id": "REQUESTER", "name": "报修员"},
        {"id": "ENERGY", "name": "能源管理员"},
    ]


@router.post("/technician-profile-requests")
def submit_profile_request(
    body: ProfileChangeBody,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if user.get("role") != "ops":
        raise HTTPException(status_code=403, detail="仅运维工程师可提交")
    try:
        return technician_profile_requests_store.submit(
            str(user["username"]),
            body.region.strip(),
            body.skillLevel.strip(),
            body.contactPhone.strip(),
            body.attachmentFilename.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/technician-profile-requests/mine")
def my_profile_request(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") != "ops":
        raise HTTPException(status_code=403, detail="仅运维工程师可查看")
    pending = technician_profile_requests_store.my_pending(str(user["username"]))
    return pending or {}


@router.get("/technician-profile-requests")
def list_profile_requests(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看")
    return technician_profile_requests_store.list_pending()


@router.post("/technician-profile-requests/{request_id}/approve")
def approve_profile_request(
    request_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可审批")
    try:
        return technician_profile_requests_store.approve(request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/technician-profile-requests/{request_id}/reject")
def reject_profile_request(
    request_id: int,
    body: RejectProfileBody | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可审批")
    try:
        return technician_profile_requests_store.reject(request_id, body.reason if body else None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/location/reverse")
def reverse_location(
    lng: float = Query(..., description="经度"),
    lat: float = Query(..., description="纬度"),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    if user.get("role") not in {"admin", "requester", "ops"}:
        raise HTTPException(status_code=403, detail="无权限使用定位服务")
    try:
        return amap_service.reverse_geocode(lng, lat)
    except ValueError as e:
        msg = str(e)
        if "未配置高德" in msg:
            raise HTTPException(status_code=503, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e


@router.get("/location/status")
def location_status(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, bool]:
    if user.get("role") not in {"admin", "requester", "ops"}:
        raise HTTPException(status_code=403, detail="无权限")
    return {"configured": amap_service.is_configured()}


@router.post("/attachments")
async def upload_attachment(
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    if user.get("role") not in {"admin", "requester", "ops"}:
        raise HTTPException(status_code=403, detail="无权限上传附件")
    ext = Path(file.filename or "upload.bin").suffix or ".bin"
    name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / name
    content = await file.read()
    dest.write_bytes(content)
    return {"filename": name}


@router.get("/attachments/{filename}")
def get_attachment(filename: str) -> StreamingResponse:
    safe = Path(filename).name
    path = UPLOAD_DIR / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="附件不存在")
    return StreamingResponse(path.open("rb"), media_type="application/octet-stream")


@router.get("/export/work-orders")
def export_work_orders(user: dict[str, Any] = Depends(get_current_user)) -> StreamingResponse:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可导出")
    rows = incidents_store.list_incidents(limit=5000)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "order_no", "title", "status", "requester", "technician_name", "created_at"])
    for r in rows:
        writer.writerow(
            [
                r.get("id"),
                r.get("order_no"),
                r.get("title"),
                r.get("wo_status") or r.get("status"),
                r.get("requester"),
                r.get("technician_name"),
                r.get("created_at"),
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="work-orders.csv"'},
    )


@router.get("/export/statistics")
def export_statistics(user: dict[str, Any] = Depends(get_current_user)) -> StreamingResponse:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可导出")
    rows = incidents_store.list_incidents(limit=5000)
    counts: dict[str, int] = {}
    for r in rows:
        st = str(r.get("wo_status") or r.get("status") or "UNKNOWN")
        counts[st] = counts.get(st, 0) + 1
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["status", "count"])
    for st, n in sorted(counts.items()):
        writer.writerow([st, n])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="statistics.csv"'},
    )
