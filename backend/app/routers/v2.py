from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services import v2_service
from app.services.v2_report_export import build_report_bytes

router = APIRouter(prefix="/v2", tags=["v2-upgrade"])


class VisionAnalyzeReq(BaseModel):
    filename: str | None = None


@router.post("/vision/analyze")
def vision_analyze(body: VisionAnalyzeReq) -> dict[str, Any]:
    return v2_service.vision_analyze(filename=body.filename)


@router.post("/vision/upload")
async def vision_upload(
    file: UploadFile = File(...),
    mode: str | None = Query(
        "world",
        description="视觉模型：world 或 yolo12",
    ),
    prompt: str | None = Query(None),
    conf: float | None = Query(
        None,
        ge=0.02,
        le=0.95,
        description="YOLO-World 置信度阈值；不传则默认 0.30，并在零检测时自动降低重试",
    ),
    iou: float | None = Query(
        None,
        ge=0.2,
        le=0.95,
        description="NMS IoU；不传读环境变量 YOLO_WORLD_IOU，默认 0.42",
    ),
    imgsz: int | None = Query(
        None,
        ge=640,
        le=2048,
        description="推理输入边长；不传读环境变量 YOLO_WORLD_IMGSZ，默认 1280",
    ),
) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="empty filename")
    try:
        total = 0
        chunks: list[bytes] = []
        while True:
            part = await file.read(1024 * 1024)
            if not part:
                break
            total += len(part)
            if total > v2_service.MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="file too large (max 50MB)")
            chunks.append(part)
        raw = b"".join(chunks)
        path = v2_service.save_upload_temp(raw, file.filename)
        return v2_service.vision_analyze_saved(
            path,
            file.filename,
            prompt=prompt,
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            mode=mode,
        )
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)[:1200]
        out = v2_service.vision_analyze(filename=file.filename)
        out["saved_path"] = None
        out["upload_or_vision_error"] = msg
        out["yolo"] = {"available": False, "hint": "上传/保存/推理前异常（已避免 500）", "error": msg}
        return out


@router.get("/twin/scene")
def twin_scene(building_id: str | None = Query(None)) -> dict[str, Any]:
    return v2_service.twin_scene(building_id=building_id)


@router.get("/ops/indicators")
def ops_indicators(building_id: str | None = Query(None)) -> dict[str, Any]:
    return v2_service.ops_indicators(building_id=building_id)


@router.get("/ops/suggestions")
def ops_suggestions(building_id: str | None = Query(None)) -> dict[str, Any]:
    return v2_service.ops_suggestions(building_id=building_id)


@router.get("/forecast/energy")
def forecast_energy(
    building_id: str | None = Query(None),
    horizon_hours: int = Query(24, ge=6, le=168),
) -> dict[str, Any]:
    return v2_service.forecast_energy(building_id=building_id, horizon_hours=horizon_hours)


class ApplianceForecastItem(BaseModel):
    label: str
    bbox_index: int = 0
    integrity_score: float | None = None
    category_zh: str | None = None


class ApplianceForecastBody(BaseModel):
    horizon_hours: int = Field(48, ge=6, le=168)
    appliances: list[ApplianceForecastItem] = Field(default_factory=list)


@router.post("/forecast/appliances")
def forecast_appliances(body: ApplianceForecastBody) -> dict[str, Any]:
    horizon = max(6, min(168, int(body.horizon_hours or 48)))
    items = [a.model_dump() for a in body.appliances]
    return v2_service.forecast_appliances(items, horizon_hours=horizon)


@router.get("/reports/{kind}")
def reports_export(
    kind: str,
    building_id: str | None = Query(None),
    file_format: str = Query("word", pattern="^(word|pdf)$"),
) -> Response:
    if kind not in {"operations", "esg"}:
        raise HTTPException(status_code=400, detail="kind must be operations or esg")
    body, filename, media = build_report_bytes(kind, file_format, building_id=building_id)
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
