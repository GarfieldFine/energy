from __future__ import annotations

import math
import os
import threading
import uuid
import zlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.energy_store import load_energy

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"
# v2_service.py 位于 backend/app/services/，parents[2] 为 backend 根目录（便于放本地 .pt）
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _env_float(name: str, default: float, lo: float, hi: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(lo, min(hi, float(raw)))
    except ValueError:
        return default


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(lo, min(hi, int(float(raw))))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


# YOLO-World v2：开放词汇；同系列中 x-worldv2 精度最高（仍属 YOLOv8-world 权重命名）
_DEFAULT_YOLO_WORLD_WEIGHT = "yolov8x-worldv2.pt"
_DEFAULT_YOLO12_WEIGHT = "yolo12x.pt"


def _yolo_world_weights_path() -> str:
    explicit = (os.environ.get("YOLO_WORLD_MODEL") or "").strip()
    if explicit:
        ep = Path(explicit)
        if ep.is_file():
            return str(ep.resolve())
        return explicit
    local = _BACKEND_ROOT / _DEFAULT_YOLO_WORLD_WEIGHT
    if local.is_file():
        return str(local.resolve())
    return _DEFAULT_YOLO_WORLD_WEIGHT


_YOLO_WORLD_MODEL = None
_YOLO12_MODEL = None
# 兼容旧字段：错误信息/日志用默认名；实际加载路径见 _yolo_world_weights_path()
_YOLO_WORLD_MODEL_NAME = _DEFAULT_YOLO_WORLD_WEIGHT
_YOLO12_MODEL_NAME = _DEFAULT_YOLO12_WEIGHT


def _yolo12_weights_path() -> str:
    explicit = (os.environ.get("YOLO12_MODEL") or "").strip()
    if explicit:
        ep = Path(explicit)
        if ep.is_file():
            return str(ep.resolve())
        return explicit
    local = _BACKEND_ROOT / _DEFAULT_YOLO12_WEIGHT
    if local.is_file():
        return str(local.resolve())
    return _DEFAULT_YOLO12_WEIGHT

# ultralytics 默认复用 model.predictor；多请求并发或 YOLO-World 动态 set_classes 后不复位会导致「只第一次识别正常」
_YOLO_INFER_LOCK = threading.Lock()


def _reset_ultralytics_predictor(m: Any) -> None:
    if m is not None:
        m.predictor = None

# 默认英文类名（逗号分隔可扩展）；用户可通过 query prompt 覆盖
_INDOOR_CLASSES_DEFAULT: tuple[str, ...] = (
    "person",
    "bed",
    "sofa",
    "couch",
    "chair",
    "bench",
    "stool",
    "dining table",
    "coffee table",
    "desk",
    "nightstand",
    "tv",
    "monitor",
    "laptop",
    "keyboard",
    "mouse",
    # 台灯附近扁平物体易被误标为 book；显式类名 + 后处理几何规则缓解
    "lamp",
    "lamp base",
    "lamp stand",
    "desk mat",
    "mouse pad",
    "coaster",
    "light",
    "book",
    "shelf",
    "bookshelf",
    "cabinet",
    "wardrobe",
    "refrigerator",
    "oven",
    "toaster",
    "sink",
    "bathtub",
    "toilet",
    "shower",
    "ceiling fan",
    "fan",
    "air conditioner",
    "radiator",
    "curtain",
    "blinds",
    "potted plant",
    "vase",
    "clock",
    "mirror",
    "picture frame",
    "rug",
    "carpet",
    "pillow",
    "blanket",
    "door",
    "window",
    "trash can",
    "vacuum cleaner",
    "backpack",
    "handbag",
    "bottle",
    "cup",
    "bowl",
    "remote",
    "cell phone",
)

# YOLO-World 一次挂太多类名时召回可能很差；零结果时自动用少量常见类重试
_INDOOR_CLASSES_FALLBACK: tuple[str, ...] = (
    "person",
    "chair",
    "desk",
    "table",
    "dining table",
    "monitor",
    "laptop",
    "keyboard",
    "window",
    "door",
    "lamp",
    "lamp base",
    "light",
    "sofa",
    "cabinet",
    "book",
)


def vision_analyze(filename: str | None = None) -> dict[str, Any]:
    """
    演示级视觉分析（文件名启发）；上传接口叠加 YOLO-World 检测。
    """
    name = (filename or "").lower()
    room_type = "office"
    if "meeting" in name or "会议" in name:
        room_type = "meeting_room"
    elif "机房" in name or "server" in name:
        room_type = "server_room"

    return {
        "room_type": room_type,
        "people_count": 0 if "empty" in name else 3,
        "density": 0.12 if "empty" in name else 0.55,
        "devices": {"ac_on": True, "lights_on": True, "pc_on": True},
        "lighting_level": "normal",
        "curtain_state": "half_open",
        "confidence": 0.86,
        "note": "文件名规则为演示占位；上传图片时可叠加 YOLO-World（pip install -U ultralytics）",
    }


def _parse_indoor_classes(prompt: str | None) -> list[str]:
    if prompt and prompt.strip():
        parts = [p.strip() for p in prompt.replace("，", ",").split(",")]
        out = [p for p in parts if p]
        return out[:120]
    return list(_INDOOR_CLASSES_DEFAULT)


def _tensor_item(x: Any) -> float | int:
    """标量 tensor / numpy -> Python 数值。"""
    try:
        if hasattr(x, "detach"):
            return float(x.detach().cpu().numpy().reshape(-1)[0])
        if hasattr(x, "item"):
            return x.item()
    except Exception:
        pass
    return float(x)


def _boxes_and_masks_from_result(r0: Any) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    解析 ultralytics Result。YOLO-World / 新版 tensor API 下批量 .tolist() 可能异常，
    若整段失败会导致「count>0 但 boxes 空」；改为逐框索引解析。
    """
    counts: dict[str, int] = {}
    boxes_out: list[dict[str, Any]] = []
    masks_out: list[dict[str, Any]] = []
    bx = getattr(r0, "boxes", None)
    if bx is None:
        return counts, boxes_out, masks_out
    try:
        n = len(bx)
    except Exception:
        return counts, boxes_out, masks_out
    if n <= 0:
        return counts, boxes_out, masks_out

    names = getattr(r0, "names", None) or {}

    # 优先用 Boxes.data（N×6：xyxy + conf + cls），与 ultralytics 内部一致，最稳
    data = getattr(bx, "data", None)
    if data is not None:
        try:
            arr = data.detach().cpu().numpy() if hasattr(data, "detach") else data.cpu().numpy()
            if arr is not None and getattr(arr, "size", 0) > 0:
                arr = arr.reshape(-1, arr.shape[-1]) if arr.ndim > 1 else arr.reshape(1, -1)
                for row in arr[:200]:
                    flat = row.reshape(-1)
                    if flat.size < 6:
                        continue
                    x1, y1, x2, y2 = float(flat[0]), float(flat[1]), float(flat[2]), float(flat[3])
                    conf_v = float(flat[4])
                    ci = int(flat[5])
                    label = str(names.get(ci, ci))
                    counts[label] = counts.get(label, 0) + 1
                    boxes_out.append(
                        {
                            "label": label,
                            "conf": conf_v,
                            "bbox_xyxy": [x1, y1, x2, y2],
                        }
                    )
        except Exception:
            counts = {}
            boxes_out = []

    if not boxes_out:
        for i in range(min(n, 200)):
            try:
                row = bx.xyxy[i]
                if hasattr(row, "cpu"):
                    row = row.cpu().detach().numpy().ravel()
                elif hasattr(row, "numpy"):
                    row = row.numpy().ravel()
                else:
                    row = row
                coords = [float(x) for x in (row.tolist() if hasattr(row, "tolist") else list(row))]
                if len(coords) < 4:
                    continue
                x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]

                ci_raw = bx.cls[i]
                ci = int(_tensor_item(ci_raw))
                label = str(names.get(ci, ci))

                conf: float | None = None
                if getattr(bx, "conf", None) is not None:
                    try:
                        conf = float(_tensor_item(bx.conf[i]))
                    except Exception:
                        conf = None

                counts[label] = counts.get(label, 0) + 1
                boxes_out.append(
                    {
                        "label": label,
                        "conf": conf,
                        "bbox_xyxy": [x1, y1, x2, y2],
                    }
                )
            except Exception:
                continue

    try:
        if getattr(r0, "masks", None) is not None and getattr(r0.masks, "xy", None) is not None:
            for i, poly in enumerate(r0.masks.xy[:80]):
                if i >= len(boxes_out):
                    break
                pts = [[float(x), float(y)] for x, y in poly.tolist()] if hasattr(poly, "tolist") else []
                if not pts:
                    continue
                masks_out.append({"i": i, "label": boxes_out[i]["label"], "polygon_xy": pts[:200]})
    except Exception:
        masks_out = []
    return counts, boxes_out, masks_out


def _bbox_xyxy_from_item(box: dict[str, Any]) -> list[float] | None:
    xy = box.get("bbox_xyxy") or box.get("bbox")
    if not isinstance(xy, (list, tuple)) or len(xy) < 4:
        return None
    return [float(xy[0]), float(xy[1]), float(xy[2]), float(xy[3])]


def _xyxy_area(b: list[float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _iou_xyxy(a: list[float], b: list[float]) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = _xyxy_area(a) + _xyxy_area(b) - inter
    if ua <= 1e-9:
        return 0.0
    return inter / ua


def _counts_from_boxes(boxes: list[dict[str, Any]]) -> dict[str, int]:
    c: dict[str, int] = {}
    for b in boxes:
        lb = str(b.get("label") or "object")
        c[lb] = c.get(lb, 0) + 1
    return c


def _refine_yolo_world_book_under_lamp(boxes: list[dict[str, Any]]) -> None:
    """台灯光轴下垫台常被误标为 book：与 lamp 框竖直/水平对齐的 book 改为 lamp base。"""
    if (os.environ.get("YOLO_WORLD_SKIP_BOOK_REFINE") or "").strip().lower() in ("1", "true", "yes", "on"):
        return
    lamps: list[list[float]] = []
    for b in boxes:
        lab = str(b.get("label") or "").lower()
        if "lamp" not in lab or "clamp" in lab:
            continue
        bb = _bbox_xyxy_from_item(b)
        if bb and _xyxy_area(bb) > 1e-6:
            lamps.append(bb)
    if not lamps:
        return

    for b in boxes:
        lab = str(b.get("label") or "").lower()
        if lab != "book":
            continue
        bb = _bbox_xyxy_from_item(b)
        if not bb:
            continue
        bw = bb[2] - bb[0]
        bh = bb[3] - bb[1]
        if bw < 4 or bh < 4:
            continue
        ar = bw / bh
        if ar < 0.45 or ar > 4.2:
            continue
        bcx = (bb[0] + bb[2]) / 2
        bcy = (bb[1] + bb[3]) / 2
        ba = _xyxy_area(bb)
        for lb in lamps:
            lx1, ly1, lx2, ly2 = lb
            lw = lx2 - lx1
            lh = ly2 - ly1
            if lw < 4 or lh < 4:
                continue
            lcx = (lx1 + lx2) / 2
            la = _xyxy_area(lb)
            if abs(bcx - lcx) > 0.52 * max(lw, bw):
                continue
            iou_v = _iou_xyxy(bb, lb)
            tol = max(12.0, 0.16 * lh)
            below_mid = bcy > ly1 + 0.38 * lh
            under_bottom = bb[1] >= ly2 - tol
            if not (below_mid or under_bottom or iou_v >= 0.03):
                continue
            if ba > la * 3.0:
                continue
            b["label"] = "lamp base"
            break


def _refine_yolo_world_microwave_vs_ac(boxes: list[dict[str, Any]], image_size: dict[str, int] | None) -> None:
    """
    挂壁空调在室内图中常被误标为 microwave：
    若 microwave 框处于上墙高位、横向细长且面积接近空调常见尺度，则改为 air conditioner。
    """
    if (os.environ.get("YOLO_WORLD_SKIP_AC_REFINE") or "").strip().lower() in ("1", "true", "yes", "on"):
        return
    if not image_size:
        return
    iw = float(image_size.get("w") or 0)
    ih = float(image_size.get("h") or 0)
    if iw < 16 or ih < 16:
        return
    img_area = max(iw * ih, 1.0)
    labels = [str(b.get("label") or "").lower().strip() for b in boxes]
    kitchen_cues = (
        "sink",
        "oven",
        "toaster",
        "refrigerator",
        "cabinet",
        "dining table",
        "kitchen",
    )
    has_kitchen_context = any(any(k in lb for k in kitchen_cues) for lb in labels)
    for b in boxes:
        lab = str(b.get("label") or "").lower().strip()
        if not _is_microwave_label(lab):
            continue
        bb = _bbox_xyxy_from_item(b)
        if not bb:
            continue
        x1, y1, x2, y2 = bb
        bw = max(0.0, x2 - x1)
        bh = max(0.0, y2 - y1)
        if bw < 6 or bh < 6:
            continue
        ar = bw / max(bh, 1e-6)
        rel_area = (bw * bh) / img_area
        cy = (y1 + y2) * 0.5
        near_upper_wall = (cy / ih) <= 0.45
        elongated = ar >= 1.55
        ac_like_scale = 0.006 <= rel_area <= 0.180
        # 非厨房语境下，上墙细长目标默认优先视为挂机空调
        if near_upper_wall and elongated and ac_like_scale and (not has_kitchen_context):
            b["label"] = "air conditioner"
            continue
        # 有厨房语境时保持更保守
        if near_upper_wall and ar >= 1.9 and (0.008 <= rel_area <= 0.120):
            b["label"] = "air conditioner"


def _is_microwave_label(label: str) -> bool:
    s = (label or "").lower().strip().replace("_", " ")
    return ("microwave" in s) or ("microwave oven" in s)


def _suppress_microwave_near_ac(boxes: list[dict[str, Any]], image_size: dict[str, int] | None) -> None:
    """
    去除与空调高重叠的 microwave 残留框，避免同一目标双标签。
    """
    if not boxes:
        return
    iw = float((image_size or {}).get("w") or 0)
    ih = float((image_size or {}).get("h") or 0)
    ac_boxes: list[list[float]] = []
    for b in boxes:
        if str(b.get("label") or "").lower().strip() != "air conditioner":
            continue
        bb = _bbox_xyxy_from_item(b)
        if bb and _xyxy_area(bb) > 1e-6:
            ac_boxes.append(bb)
    if not ac_boxes:
        return

    kept: list[dict[str, Any]] = []
    for b in boxes:
        lab = str(b.get("label") or "").lower().strip()
        if not _is_microwave_label(lab):
            kept.append(b)
            continue
        bb = _bbox_xyxy_from_item(b)
        if not bb:
            kept.append(b)
            continue
        bw = max(0.0, bb[2] - bb[0])
        bh = max(0.0, bb[3] - bb[1])
        if bw < 6 or bh < 6:
            kept.append(b)
            continue
        ar = bw / max(bh, 1e-6)
        cy_ratio = ((bb[1] + bb[3]) * 0.5 / ih) if ih > 1 else 1.0
        near_upper_wall = cy_ratio <= 0.5
        overlaps_ac = any(_iou_xyxy(bb, ab) >= 0.08 for ab in ac_boxes)
        # 检测到空调时，对重叠 microwave 从严去除；并继续过滤上墙细长框
        if overlaps_ac:
            continue
        if near_upper_wall and ar >= 1.6:
            continue
        kept.append(b)
    boxes[:] = kept


def _suppress_microwave_by_context(boxes: list[dict[str, Any]], image_size: dict[str, int] | None) -> None:
    """
    在非厨房语境下强抑制 microwave 误检。
    经验规则：
    - 无厨房线索（sink/oven/toaster/refrigerator 等）时，microwave 默认从严过滤；
    - 有厨房线索时，仅保留更接近台面尺度与位置的 microwave。
    """
    if not boxes:
        return
    iw = float((image_size or {}).get("w") or 0)
    ih = float((image_size or {}).get("h") or 0)
    if iw < 16 or ih < 16:
        return
    img_area = max(iw * ih, 1.0)

    labels = [str(b.get("label") or "").lower().strip() for b in boxes]
    kitchen_cues = (
        "sink",
        "oven",
        "toaster",
        "refrigerator",
        "cabinet",
        "dining table",
        "kitchen",
    )
    has_kitchen_context = any(any(k in lb for k in kitchen_cues) for lb in labels)
    has_air_conditioner = any("air conditioner" in lb for lb in labels)

    kept: list[dict[str, Any]] = []
    for b in boxes:
        lab = str(b.get("label") or "").lower().strip()
        if not _is_microwave_label(lab):
            kept.append(b)
            continue
        bb = _bbox_xyxy_from_item(b)
        if not bb:
            continue
        x1, y1, x2, y2 = bb
        bw = max(0.0, x2 - x1)
        bh = max(0.0, y2 - y1)
        if bw < 6 or bh < 6:
            continue
        area_r = (bw * bh) / img_area
        ar = bw / max(bh, 1e-6)
        cy_r = ((y1 + y2) * 0.5) / ih

        # 台面微波炉更常见于中下部、形态不过分细长、面积中等
        countertop_like = (0.35 <= cy_r <= 0.88) and (0.8 <= ar <= 2.6) and (0.004 <= area_r <= 0.09)
        # 上墙高位且偏细长，明显更像挂机空调
        ac_like = (cy_r <= 0.52) and (ar >= 1.55)

        # 只要同图出现空调，默认剔除 microwave（办公/会议场景误检远多于真实共存）
        if has_air_conditioner:
            continue

        if not has_kitchen_context:
            # 非厨房语境：仅在非常像台面微波炉时保留
            if countertop_like and not ac_like:
                kept.append(b)
            continue

        # 有厨房线索：放宽，但空调形态仍抑制
        if ac_like:
            continue
        if area_r < 0.0025 or area_r > 0.12:
            continue
        kept.append(b)
    boxes[:] = kept


def _sync_mask_labels(boxes: list[dict[str, Any]], masks: list[dict[str, Any]]) -> None:
    for m in masks:
        try:
            ii = int(m.get("i", -1))
        except (TypeError, ValueError):
            continue
        if 0 <= ii < len(boxes):
            m["label"] = boxes[ii]["label"]


def _orig_shape_from_result(r0: Any) -> dict[str, int] | None:
    try:
        if getattr(r0, "orig_shape", None):
            oh, ow = r0.orig_shape
            return {"w": int(ow), "h": int(oh)}
    except Exception:
        pass
    return None


def _run_yolo_world(
    path: Path,
    prompt: str | None,
    conf: float | None = None,
    iou: float | None = None,
    imgsz: int | None = None,
) -> dict[str, Any]:
    """
    Ultralytics YOLO-World：开放词汇检测，室内场景可一次设定大量英文类名。
    每次请求都会 predict 当前上传文件；模型实例全局缓存仅为省加载时间，不缓存图像结果。
    参考：https://docs.ultralytics.com/models/yolo-world/
    """
    global _YOLO_WORLD_MODEL
    try:
        from ultralytics import YOLO
    except ImportError:
        return {"available": False, "hint": "可选依赖：pip install -U 'ultralytics>=8.3'（将自动下载 yolov8x-worldv2.pt 等）"}

    base_conf = 0.30 if conf is None else max(0.02, min(0.95, float(conf)))

    user_classes = _parse_indoor_classes(prompt)
    if not user_classes:
        user_classes = list(_INDOOR_CLASSES_DEFAULT)

    weights_path = _yolo_world_weights_path()
    # 略收紧默认 IoU，减少同类重复框，观感更「准」（可用 query / 环境变量覆盖）
    iou_used = max(0.2, min(0.95, float(iou))) if iou is not None else _env_float("YOLO_WORLD_IOU", 0.42, 0.2, 0.95)
    imgsz_used = max(640, min(2048, int(imgsz))) if imgsz is not None else _env_int("YOLO_WORLD_IMGSZ", 1280, 640, 2048)
    augment_used = _env_bool("YOLO_WORLD_AUGMENT", False)
    max_det_used = _env_int("YOLO_WORLD_MAX_DET", 250, 50, 500)

    with _YOLO_INFER_LOCK:
        if _YOLO_WORLD_MODEL is None:
            try:
                _YOLO_WORLD_MODEL = YOLO(weights_path)
            except Exception as e:
                msg = str(e)
                if len(msg) > 500:
                    msg = msg[:500] + "..."
                return {
                    "available": False,
                    "hint": "加载 YOLO-World 权重失败（需联网首次下载，或升级 ultralytics：pip install -U ultralytics）",
                    "error": msg,
                    "model": Path(weights_path).name,
                    "weights_path": weights_path,
                }

        return _run_yolo_world_core(
            path,
            user_classes,
            base_conf,
            weights_path=weights_path,
            iou_used=iou_used,
            imgsz_used=imgsz_used,
            augment_used=augment_used,
            max_det_used=max_det_used,
        )


def _run_yolo12(
    path: Path,
    conf: float | None = None,
    iou: float | None = None,
    imgsz: int | None = None,
) -> dict[str, Any]:
    """YOLO12 通用检测（封闭类别）。"""
    global _YOLO12_MODEL
    try:
        from ultralytics import YOLO
    except ImportError:
        return {"available": False, "hint": "可选依赖：pip install -U 'ultralytics>=8.3'"}

    base_conf = 0.30 if conf is None else max(0.02, min(0.95, float(conf)))
    iou_used = max(0.2, min(0.95, float(iou))) if iou is not None else _env_float("YOLO12_IOU", 0.45, 0.2, 0.95)
    imgsz_used = max(640, min(2048, int(imgsz))) if imgsz is not None else _env_int("YOLO12_IMGSZ", 1280, 640, 2048)
    augment_used = _env_bool("YOLO12_AUGMENT", False)
    max_det_used = _env_int("YOLO12_MAX_DET", 250, 50, 500)
    weights_path = _yolo12_weights_path()

    with _YOLO_INFER_LOCK:
        if _YOLO12_MODEL is None:
            try:
                _YOLO12_MODEL = YOLO(weights_path)
            except Exception as e:
                msg = str(e)
                if len(msg) > 500:
                    msg = msg[:500] + "..."
                return {
                    "available": False,
                    "hint": "加载 YOLO12 权重失败（可在 backend 根目录放置 yolo12x.pt，或设置 YOLO12_MODEL）",
                    "error": msg,
                    "model": Path(weights_path).name,
                    "weights_path": weights_path,
                }

        attempts: list[tuple[str, float, int]] = [
            ("default", base_conf, imgsz_used),
            ("low_conf", min(base_conf, 0.08), imgsz_used),
        ]
        hi = min(2048, imgsz_used + 256)
        if hi > imgsz_used:
            attempts.append(("high_res", base_conf, hi))

        r0: Any = None
        counts: dict[str, int] = {}
        boxes_out: list[dict[str, Any]] = []
        masks_out: list[dict[str, Any]] = []
        image_size: dict[str, int] | None = None
        tried: list[str] = []
        last_conf = base_conf

        for tag, cf, this_imgsz in attempts:
            last_conf = cf
            _reset_ultralytics_predictor(_YOLO12_MODEL)
            try:
                results = _YOLO12_MODEL.predict(
                    str(path),
                    verbose=False,
                    conf=cf,
                    iou=iou_used,
                    imgsz=this_imgsz,
                    max_det=max_det_used,
                    augment=augment_used,
                )
            except Exception as e:
                msg = str(e)
                if len(msg) > 500:
                    msg = msg[:500] + "..."
                if tag == "default":
                    return {
                        "available": False,
                        "hint": "YOLO12 推理失败",
                        "error": msg,
                        "model": Path(weights_path).name,
                        "weights_path": weights_path,
                    }
                tried.append(f"{tag}:predict_failed")
                continue
            if not results:
                tried.append(f"{tag}:empty_results")
                continue

            r0 = results[0]
            counts, boxes_out, masks_out = _boxes_and_masks_from_result(r0)
            image_size = _orig_shape_from_result(r0)
            tried.append(f"{tag}:conf={cf:.3f}:iou={iou_used:.2f}:imgsz={this_imgsz}:parsed_boxes={len(boxes_out)}")
            if boxes_out:
                break

        if r0 is None:
            return {
                "available": True,
                "pipeline": "yolo12",
                "model": Path(weights_path).name,
                "weights_path": weights_path,
                "detections": {},
                "count": 0,
                "boxes": [],
                "masks": [],
                "image_size": None,
                "conf_used": last_conf,
                "iou_used": iou_used,
                "imgsz_used": imgsz_used,
                "augment_used": augment_used,
                "max_det_used": max_det_used,
                "inference_attempts": tried,
                "note": "YOLO12 未检测到目标：已自动低阈值与高分辨率重试。",
            }

        return {
            "available": True,
            "pipeline": "yolo12",
            "model": Path(weights_path).name,
            "weights_path": weights_path,
            "detections": counts,
            "count": len(boxes_out),
            "boxes": boxes_out[:120],
            "masks": masks_out,
            "image_size": image_size,
            "conf_used": last_conf,
            "iou_used": iou_used,
            "imgsz_used": imgsz_used,
            "augment_used": augment_used,
            "max_det_used": max_det_used,
            "inference_attempts": tried,
            "note": "YOLO12 通用检测；类别由模型预训练词表决定。",
        }


def _run_yolo_world_core(
    path: Path,
    user_classes: list[str],
    base_conf: float,
    *,
    weights_path: str,
    iou_used: float,
    imgsz_used: int,
    augment_used: bool,
    max_det_used: int,
) -> dict[str, Any]:
    """在 _YOLO_INFER_LOCK 内调用；set_classes 后必须 reset predictor，否则 ultralytics 复用 AutoBackend 时常见只认第一次图源。"""
    global _YOLO_WORLD_MODEL

    # 多轮：全量类 + 用户 conf → 更低 conf → 少量常见类 → 提高 imgsz 再试（零结果时抬召回）
    attempts: list[tuple[str, list[str], float, int | None]] = [
        ("default", user_classes, base_conf, None),
        ("low_conf", user_classes, min(base_conf, 0.05), None),
        ("fallback_classes", list(_INDOOR_CLASSES_FALLBACK), 0.08, None),
    ]
    if (os.environ.get("YOLO_WORLD_SKIP_HIGH_RES_RETRY") or "").strip().lower() not in ("1", "true", "yes", "on"):
        hi = min(2048, imgsz_used + 256)
        if hi > imgsz_used:
            attempts.append(("high_res", user_classes, base_conf, hi))

    r0: Any = None
    counts: dict[str, int] = {}
    boxes_out: list[dict[str, Any]] = []
    masks_out: list[dict[str, Any]] = []
    image_size: dict[str, int] | None = None
    classes_used: list[str] = user_classes
    tried: list[str] = []
    last_conf = base_conf

    for tag, cls_list, cf, imgsz_override in attempts:
        last_conf = cf
        this_imgsz = imgsz_override if imgsz_override is not None else imgsz_used
        try:
            _YOLO_WORLD_MODEL.set_classes(cls_list)
        except Exception as e:
            msg = str(e)
            if len(msg) > 500:
                msg = msg[:500] + "..."
            if tag == "default":
                hint = "set_classes 失败：请升级 ultralytics 至 8.3.155+（YOLO-World 动态类别修复）"
                low = msg.lower()
                if "no module named 'clip'" in low or "modulenotfounderror" in low and "clip" in low:
                    hint = (
                        "YOLO-World 需要 OpenAI CLIP（import clip）。请安装："
                        "pip install git+https://github.com/openai/CLIP.git"
                        "（或 pip install -r backend/requirements-v2-vision.txt），然后重启后端。"
                    )
                return {
                    "available": False,
                    "hint": hint,
                    "error": msg,
                    "model": Path(weights_path).name,
                    "weights_path": weights_path,
                    "classes_preview": cls_list[:30],
                }
            tried.append(f"{tag}:set_classes_failed")
            continue

        _reset_ultralytics_predictor(_YOLO_WORLD_MODEL)

        try:
            results = _YOLO_WORLD_MODEL.predict(
                str(path),
                verbose=False,
                conf=cf,
                iou=iou_used,
                imgsz=this_imgsz,
                max_det=max_det_used,
                augment=augment_used,
            )
        except Exception as e:
            msg = str(e)
            if len(msg) > 500:
                msg = msg[:500] + "..."
            if tag == "default":
                return {
                    "available": False,
                    "hint": "YOLO-World 推理失败",
                    "error": msg,
                    "model": Path(weights_path).name,
                    "weights_path": weights_path,
                    "classes_preview": cls_list[:30],
                }
            tried.append(f"{tag}:predict_failed")
            continue

        if not results:
            tried.append(f"{tag}:empty_results")
            continue

        r0 = results[0]
        counts, boxes_out, masks_out = _boxes_and_masks_from_result(r0)
        _refine_yolo_world_book_under_lamp(boxes_out)
        image_size = _orig_shape_from_result(r0)
        _refine_yolo_world_microwave_vs_ac(boxes_out, image_size)
        _suppress_microwave_near_ac(boxes_out, image_size)
        _suppress_microwave_by_context(boxes_out, image_size)
        counts = _counts_from_boxes(boxes_out)
        _sync_mask_labels(boxes_out, masks_out)
        classes_used = cls_list
        tried.append(
            f"{tag}:conf={cf:.3f}:iou={iou_used:.2f}:imgsz={this_imgsz}:aug={int(augment_used)}:parsed_boxes={len(boxes_out)}"
        )
        if len(boxes_out) > 0:
            break

    if r0 is None:
        return {
            "available": True,
            "pipeline": "yolo_world",
            "model": Path(weights_path).name,
            "weights_path": weights_path,
            "detections": {},
            "count": 0,
            "boxes": [],
            "masks": [],
            "image_size": None,
            "classes_used": user_classes,
            "conf_used": last_conf,
            "iou_used": iou_used,
            "imgsz_used": imgsz_used,
            "augment_used": augment_used,
            "max_det_used": max_det_used,
            "inference_attempts": tried,
            "note": "无检测结果：已重试更低置信度、精简类别与更高 imgsz；可调低 conf 或精简 prompt 类别后再试。",
        }

    cnt = len(boxes_out)
    note = (
        "YOLO-World：开放词汇；prompt 为空时使用内置室内类别表。"
        " 默认可提高精度的设置：imgsz=1280、iou=0.42（可用查询参数或环境变量 YOLO_WORLD_IMGSZ / YOLO_WORLD_IOU 覆盖）；"
        " 可选 YOLO_WORLD_AUGMENT=1 开启 TTA（更慢）。"
        " 每次上传独立推理；全局仅缓存模型权重；set_classes 后会重建 predictor。"
    )
    if tried:
        note += f" 推理记录: {' | '.join(tried)}。"

    return {
        "available": True,
        "pipeline": "yolo_world",
        "model": Path(weights_path).name,
        "weights_path": weights_path,
        "detections": counts,
        "count": cnt,
        "boxes": boxes_out[:120],
        "masks": masks_out,
        "image_size": image_size,
        "classes_used": classes_used,
        "conf_used": last_conf,
        "iou_used": iou_used,
        "imgsz_used": imgsz_used,
        "augment_used": augment_used,
        "max_det_used": max_det_used,
        "inference_attempts": tried,
        "note": note.strip(),
    }


_APPLIANCE_META: tuple[tuple[str, str, float, str], ...] = (
    ("air conditioner", "空调/制冷", 12.0, "压缩机与冷媒回路老化常伴随效率下降与电流缓慢抬升"),
    ("refrigerator", "冷藏冷冻", 14.0, "压缩机频繁启停易在尖峰段叠加负荷"),
    ("microwave", "微波加热", 8.0, "高压部件受潮老化可能带来浪涌与待机异常"),
    ("laptop", "计算机/电源", 5.0, "电源适配器老化会增加待机损耗与发热"),
    ("monitor", "显示终端", 8.0, "背光电源板异常可致局部发热与电流毛刺"),
    ("keyboard", "外设", 6.0, "有线外设短路风险低，主要关注供电口接触"),
    ("ceiling fan", "风机类", 12.0, "轴承磨损常表现为电流缓慢上升"),
    ("fan", "风机类", 12.0, "同风机类设备"),
    ("lamp", "照明", 10.0, "驱动/接触不良可致闪烁与谐波"),
    ("light", "照明", 10.0, "同照明类"),
    ("tv", "影音", 10.0, "开关电源老化影响待机功率"),
    ("television", "影音", 10.0, "同影音类"),
    ("vacuum", "清洁电器", 7.0, "电机碳刷磨损后效率下降"),
    ("toaster", "电热厨电", 8.0, "加热丝劣化可致恒温频繁启停"),
    ("oven", "电热厨电", 12.0, "加热盘老化可致启停节律变化"),
)

_ASSET_HEALTH_DISCLAIMER = (
    "演示推断：依据单帧 RGB、检测置信度与框尺度等启发式规则，"
    "不能识别真实裂纹/形变/绝缘击穿；寿命与更换建议仅供运维排程参考。"
)


def _match_appliance_meta(label: str) -> tuple[str, float, str] | None:
    s = label.lower().replace("_", " ")
    seen = set()
    for sub, zh, life, tag in _APPLIANCE_META:
        if sub in seen:
            continue
        if sub in s:
            seen.add(sub)
            return zh, life, tag
    return None


def _crc_u32(s: str) -> int:
    return zlib.crc32(s.encode("utf-8", errors="ignore")) & 0xFFFFFFFF


def assess_appliance_health_from_yolo(yolo: dict[str, Any]) -> dict[str, Any]:
    """
    演示级：在 YOLO-World 框上估计「完好度/破损倾向、剩余寿命、更换建议、用电风险提示」。
    非真实损伤检测；不替代现场电气试验。
    """
    if not yolo.get("available"):
        return {
            "available": False,
            "hint": yolo.get("hint", "视觉推理未就绪"),
            "disclaimer": _ASSET_HEALTH_DISCLAIMER,
            "items": [],
            "summary": {},
        }

    img = yolo.get("image_size") or {}
    iw = float(img.get("w") or 0) or 1.0
    ih = float(img.get("h") or 0) or 1.0
    img_area = max(iw * ih, 1.0)
    boxes = yolo.get("boxes") or []
    items: list[dict[str, Any]] = []

    for idx, b in enumerate(boxes[:80]):
        label = str(b.get("label") or "object")
        meta = _match_appliance_meta(label)
        if meta is None:
            continue
        cat_zh, design_life, elec_tag = meta
        bbox = b.get("bbox_xyxy") or b.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            continue
        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        rel_area = area / img_area
        conf = float(b.get("conf") or 0.35)
        conf = max(0.02, min(0.99, conf))

        hints: list[str] = []
        integrity = int(52 + 42 * conf)
        if rel_area < 0.0012:
            integrity -= 14
            hints.append("目标在画面中占比过小，外观细节不足")
        elif rel_area < 0.004:
            integrity -= 7
            hints.append("目标成像偏小，局部破损不易辨认")
        if conf < 0.32:
            integrity -= 10
            hints.append("检测置信度偏低")
        if conf < 0.2:
            hints.append("边界可能受遮挡/反光影响")

        tag = f"{label}|{int(x1)}|{int(y1)}|{int(x2)}|{int(y2)}"
        integrity += (_crc_u32(tag) % 9) - 4
        integrity = max(38, min(96, integrity))

        damage = 100 - integrity
        if integrity >= 86:
            dmg_lvl, replace = "良好", "可持续观察"
        elif integrity >= 73:
            dmg_lvl, replace = "轻微", "建议纳入例行巡检"
        elif integrity >= 58:
            dmg_lvl, replace = "中度", "建议近期检修并评估更换窗口"
        else:
            dmg_lvl, replace = "偏高", "建议尽快现场核查，必要时停用待检"

        life_rem = design_life * (integrity / 100.0) * (0.82 + (_crc_u32(tag + "L") % 13) / 100.0)
        life_rem = round(max(0.5, min(design_life * 1.1, life_rem)), 1)

        elec_note = elec_tag
        if integrity < 65:
            elec_note += "；设备老化或接触不良时，市电曲线在尖峰/夜间基荷段可能出现抬升或毛刺。"
        elif integrity < 78:
            elec_note += "；建议在分项计量中关注与该设备启停同步的短时突起。"

        items.append(
            {
                "bbox_index": idx,
                "label": label,
                "category_zh": cat_zh,
                "is_electric_appliance": True,
                "confidence": round(conf, 3),
                "integrity_score": integrity,
                "damage_index": damage,
                "damage_level": dmg_lvl,
                "estimated_remaining_life_years": life_rem,
                "replace_recommendation": replace,
                "electricity_risk_note": elec_note,
                "evidence_hints": hints or ["单帧未见明显结构断裂特征（演示占位）"],
            }
        )

    attn = sum(1 for it in items if int(it["integrity_score"]) < 73)
    summary = {
        "electric_appliance_detections": len(items),
        "needs_attention": attn,
        "electric_anomaly_overview": (
            "多台电热/压缩机类设备同时提示需关注时，总有功在尖峰与夜间基荷上易叠加抬升。"
            if attn >= 2
            else ""
        ),
    }
    return {"available": True, "disclaimer": _ASSET_HEALTH_DISCLAIMER, "items": items, "summary": summary}


def vision_analyze_saved(
    saved_path: Path,
    original_name: str,
    prompt: str | None = None,
    conf: float | None = None,
    iou: float | None = None,
    imgsz: int | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    out = vision_analyze(filename=original_name)
    out["saved_path"] = str(saved_path).replace("\\", "/")
    m = (mode or "world").strip().lower()
    try:
        if m in {"12", "yolo12"}:
            out["yolo"] = _run_yolo12(saved_path, conf=conf, iou=iou, imgsz=imgsz)
        else:
            out["yolo"] = _run_yolo_world(saved_path, prompt, conf=conf, iou=iou, imgsz=imgsz)
    except Exception as e:
        msg = str(e)
        if len(msg) > 1200:
            msg = msg[:1200] + "..."
        out["yolo"] = {
            "available": False,
            "hint": "视觉推理未捕获异常已转为 JSON（请查看 error）。常见原因：GPU/内存不足、ultralytics 版本与权重不兼容。",
            "error": msg,
        }
    yl = out.get("yolo") or {}
    people_like = 0
    if isinstance(yl.get("detections"), dict):
        for k in ("person", "people"):
            v = yl["detections"].get(k, 0)
            try:
                people_like += int(v)
            except (TypeError, ValueError):
                pass
    if yl.get("available") and people_like:
        out["people_count"] = int(people_like)
        out["density"] = min(1.0, 0.15 + 0.05 * people_like)
    try:
        out["asset_health"] = assess_appliance_health_from_yolo(yl if isinstance(yl, dict) else {})
    except Exception as e:
        msg = str(e)
        if len(msg) > 400:
            msg = msg[:400] + "..."
        out["asset_health"] = {
            "available": False,
            "hint": msg,
            "disclaimer": _ASSET_HEALTH_DISCLAIMER,
            "items": [],
            "summary": {},
        }
    return out


def twin_scene(building_id: str | None = None) -> dict[str, Any]:
    df = load_energy().copy()
    if building_id:
        df = df[df["building_id"] == building_id]
    if df.empty:
        return {"building_id": building_id, "floors": [], "legend": _legend()}

    df = df.sort_values("monitor_time")
    bid_last = str(df["building_id"].iloc[-1])
    sub = df[df["building_id"] == bid_last] if not building_id else df
    sub = sub.tail(min(400, len(sub)))
    n = min(5, max(3, max(1, len(sub) // 80)))
    step = max(1, len(sub) // n)
    floors: list[dict[str, Any]] = []
    for i in range(n):
        part = sub.iloc[i * step : (i + 1) * step if i < n - 1 else len(sub)]
        if part.empty:
            continue
        elec = float(pd.to_numeric(part["electricity_kwh"], errors="coerce").mean() or 0.0)
        if elec > 40:
            status = "high"
        elif elec > 20:
            status = "warning"
        else:
            status = "normal"
        floors.append(
            {
                "floor": i + 1,
                "room_id": f"F{i + 1:02d}-R01",
                "building_id": bid_last,
                "electricity_kwh": round(elec, 3),
                "status": status,
            }
        )
    return {"building_id": building_id or bid_last, "floors": floors, "legend": _legend()}


def ops_indicators(building_id: str | None = None) -> dict[str, Any]:
    df = load_energy().copy()
    if building_id:
        df = df[df["building_id"] == building_id]
    if df.empty:
        return {"rows": 0, "indicators": {"ewi": None, "dh": None}}

    e = pd.to_numeric(df.get("electricity_kwh"), errors="coerce")
    base = max(float(e.quantile(0.3)) if e.notna().any() else 1.0, 1e-6)
    e_mean = float(e.mean()) if e.notna().any() else 0.0
    e_std = float(e.std()) if e.notna().sum() > 2 else 0.0
    monitor = pd.to_datetime(df["monitor_time"])
    night_ratio = float(((monitor.dt.hour <= 5).sum()) / max(len(df), 1))
    ewi = float((e_mean / base) * night_ratio) if e.notna().any() else None

    dh = float(max(0.0, 1.0 - night_ratio * 0.35))
    return {
        "rows": int(len(df)),
        "indicators": {"ewi": round(ewi, 4) if ewi is not None else None, "dh": round(dh, 4)},
        "ops_profile": {
            "night_ratio": round(night_ratio, 4),
            "mean_kwh": round(e_mean, 4),
            "std_kwh": round(e_std, 4),
            "base_kwh": round(base, 4),
        },
        "formula_hint": {
            "ewi": "(实际能耗/基准能耗) * 无人时长占比(近似)",
            "dh": "1 - (故障次数*平均修复时间)/总运行时间(演示近似)",
        },
    }


def ops_suggestions(building_id: str | None = None) -> dict[str, Any]:
    ind = ops_indicators(building_id)
    x = ind["indicators"]
    prof = ind.get("ops_profile") or {}
    ewi = x.get("ewi") or 0.0
    dh = x.get("dh") or 1.0
    night_ratio = float(prof.get("night_ratio") or 0.0)
    mean_kwh = float(prof.get("mean_kwh") or 0.0)
    std_kwh = float(prof.get("std_kwh") or 0.0)
    base_kwh = max(float(prof.get("base_kwh") or 1.0), 1e-6)
    fluct = std_kwh / max(mean_kwh, 1e-6) if mean_kwh > 0 else 0.0
    items: list[dict[str, Any]] = []
    if ewi >= 0.7:
        items.append(
            {
                "priority": "high",
                "title": "夜间基荷偏高，建议启用非工作时段自动关停策略",
                "expected_saving_kwh_per_hour": 2.3,
            }
        )
    elif ewi >= 0.5:
        items.append(
            {
                "priority": "medium",
                "title": "夜间能耗存在抬升趋势，建议先对照门禁/排班做空调与照明分时控制。",
                "expected_effect": "夜间基荷优化",
            }
        )

    if mean_kwh >= base_kwh * 1.45 and ewi >= 0.35:
        items.append(
            {
                "priority": "medium",
                "title": "当前均值负荷明显高于基准，建议核查高耗能时段对应设备与策略设定。",
                "expected_effect": "削峰与基准回归",
            }
        )

    if fluct >= 0.42:
        items.append(
            {
                "priority": "medium",
                "title": "负荷波动偏大，建议检查启停控制逻辑与联动阈值，降低频繁波动。",
                "expected_effect": "波动收敛",
            }
        )
    elif fluct <= 0.12 and night_ratio >= 0.22:
        items.append(
            {
                "priority": "info",
                "title": "曲线波动较小但夜间占比偏高，可能存在持续基荷设备，建议做分项巡检。",
                "expected_effect": "基荷识别",
            }
        )

    if dh <= 0.75:
        items.append({"priority": "high", "title": "设备健康度下降，建议优先巡检高负荷空调/风机回路", "expected_effect": "降低故障风险"})
    elif dh <= 0.88:
        items.append({"priority": "medium", "title": "设备稳定性有轻微下滑，建议提前安排预防性保养。", "expected_effect": "降低潜在故障"})

    dedup: list[dict[str, Any]] = []
    seen_title: set[str] = set()
    for it in items:
        t = str(it.get("title") or "").strip()
        if not t or t in seen_title:
            continue
        seen_title.add(t)
        dedup.append(it)
    items = dedup[:4]
    if not items:
        items.append({"priority": "low", "title": "当前运行总体稳定，建议按周复核策略参数", "expected_effect": "保持节能表现"})
    return {"building_id": building_id, "indicators": x, "items": items}


def _forecast_naive(
    building_id: str | None,
    horizon_hours: int,
    s: pd.Series,
) -> dict[str, Any]:
    y = pd.to_numeric(s, errors="coerce").dropna()
    win = min(168, len(y))
    baseline = float(y.tail(win).mean()) if win else 0.0
    vol = float(y.tail(win).std()) if win > 2 else 0.0
    if len(y) >= 96:
        m_recent = float(y.tail(48).mean())
        m_prev = float(y.iloc[-96:-48].mean())
        slope_h = (m_recent - m_prev) / 48.0 * 0.35
    elif len(y) >= 48:
        m_recent = float(y.tail(24).mean())
        m_prev = float(y.iloc[-48:-24].mean())
        slope_h = (m_recent - m_prev) / 24.0 * 0.22
    else:
        slope_h = 0.0
    start = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    labels: list[str] = []
    values: list[float] = []
    amp = min(max(baseline * 0.11, vol * 0.42), max(baseline * 0.28, 1e-6))
    for i in range(horizon_hours):
        t0 = start + timedelta(hours=i)
        labels.append(t0.strftime("%m-%d %H:%M"))
        hour = t0.hour + t0.minute / 60.0
        diurnal = amp * math.sin(2.0 * math.pi * (hour - 6.0) / 24.0)
        raw = baseline + slope_h * i + diurnal
        values.append(round(max(0.0, float(raw)), 3))
    return {
        "building_id": building_id,
        "model": "naive_moving_average",
        "horizon_hours": horizon_hours,
        "labels": labels,
        "values": values,
    }


def forecast_energy(building_id: str | None = None, horizon_hours: int = 24) -> dict[str, Any]:
    df = load_energy().copy()
    if building_id:
        df = df[df["building_id"] == building_id]
    if df.empty:
        return {"building_id": building_id, "horizon_hours": horizon_hours, "labels": [], "values": [], "model": "none"}

    df = df.sort_values("monitor_time").tail(1500).copy()
    df["y"] = pd.to_numeric(df["electricity_kwh"], errors="coerce")
    df["ds"] = pd.to_datetime(df["monitor_time"])
    train = df.dropna(subset=["y", "ds"])[["ds", "y"]]
    if len(train) < 48:
        return _forecast_naive(building_id, horizon_hours, train["y"] if len(train) else pd.Series([0.0]))

    try:
        import logging

        logging.getLogger("prophet").setLevel(logging.ERROR)
        logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
        from prophet import Prophet

        n_train = len(train)
        weekly = n_train >= 336
        mean_y = float(pd.to_numeric(train["y"], errors="coerce").mean() or 0.0)
        season_mode = "multiplicative" if mean_y > 2.0 else "additive"
        m = Prophet(
            daily_seasonality=True,
            weekly_seasonality=weekly,
            yearly_seasonality=False,
            changepoint_prior_scale=0.08,
            seasonality_mode=season_mode,
            seasonality_prior_scale=8.0,
        )
        m.fit(train)
        future = m.make_future_dataframe(periods=horizon_hours, freq="h", include_history=False)
        fc = m.predict(future)
        labels = fc["ds"].dt.strftime("%m-%d %H:%M").tolist()
        values = [round(max(0.0, float(x)), 3) for x in fc["yhat"].tolist()]
        return {
            "building_id": building_id,
            "model": "prophet",
            "horizon_hours": horizon_hours,
            "labels": labels,
            "values": values,
        }
    except Exception as ex:
        out = _forecast_naive(building_id, horizon_hours, train["y"])
        out["model"] = "naive_fallback"
        out["prophet_error"] = str(ex)
        return out


_APPLIANCE_TYPICAL_KWH_H: tuple[tuple[str, float], ...] = (
    ("air conditioner", 1.35),
    ("refrigerator", 0.18),
    ("microwave", 0.85),
    ("laptop", 0.09),
    ("monitor", 0.07),
    ("computer", 0.12),
    ("keyboard", 0.01),
    ("ceiling fan", 0.06),
    ("fan", 0.05),
    ("lamp", 0.04),
    ("light", 0.04),
    ("tv", 0.11),
    ("television", 0.11),
    ("vacuum", 0.55),
    ("toaster", 0.75),
    ("oven", 1.1),
)


def _typical_appliance_kwh_h(label: str) -> float:
    s = label.lower().replace("_", " ")
    for sub, kw in _APPLIANCE_TYPICAL_KWH_H:
        if sub in s:
            return kw
    return 0.08


def _appliance_usage_profile_multiplier(hour: float, label: str) -> float:
    s = label.lower()
    if "lamp" in s or "light" in s:
        return 0.55 + 0.5 * max(0.0, math.sin(math.pi * (hour - 17.0) / 14.0))
    if "air conditioner" in s or " conditioner" in s:
        return 0.65 + 0.55 * max(0.0, math.sin(math.pi * (hour - 11.0) / 14.0))
    if any(k in s for k in ("laptop", "monitor", "computer", "keyboard", "tv", "television")):
        if 8.0 <= hour <= 18.0:
            return 1.0
        if hour <= 6.0 or hour >= 22.0:
            return 0.12
        return 0.35
    if "refrigerator" in s:
        return 0.88 + 0.18 * math.sin(2.0 * math.pi * (hour - 6.0) / 24.0)
    return 0.82 + 0.28 * math.sin(2.0 * math.pi * (hour - 6.0) / 24.0)


def forecast_appliances(
    appliances: list[dict[str, Any]],
    horizon_hours: int = 48,
) -> dict[str, Any]:
    """
    按视觉识别出的单个电器，基于典型功率与完好度推导分项 hourly 负荷预测（非建筑总表）。
    """
    if not appliances:
        return {
            "horizon_hours": horizon_hours,
            "model": "none",
            "scope": "per_detection",
            "appliances": [],
            "aggregated": {"labels": [], "values": [], "mean_kwh_h": None},
            "note": "无识别电器：请先完成图片识别",
        }

    start = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    labels = [(start + timedelta(hours=i)).strftime("%m-%d %H:%M") for i in range(horizon_hours)]
    out_items: list[dict[str, Any]] = []
    agg = [0.0] * horizon_hours

    for ap in appliances[:40]:
        label = str(ap.get("label") or "appliance")
        bbox_index = int(ap.get("bbox_index") or 0)
        integrity = float(ap.get("integrity_score") or 80)
        integrity = max(38.0, min(96.0, integrity))
        cat_zh = str(ap.get("category_zh") or label)
        base = _typical_appliance_kwh_h(label)
        degrade = 1.0 + max(0.0, (100.0 - integrity)) / 180.0
        seed = _crc_u32(f"{label}|{bbox_index}")

        values: list[float] = []
        for i in range(horizon_hours):
            t = start + timedelta(hours=i)
            hour = t.hour + t.minute / 60.0
            prof = _appliance_usage_profile_multiplier(hour, label)
            noise = 1.0 + ((seed + i * 17) % 11 - 5) / 100.0
            v = base * degrade * prof * noise
            values.append(round(max(0.0, float(v)), 4))
            agg[i] += v

        mean_v = sum(values) / len(values) if values else 0.0
        out_items.append(
            {
                "key": f"{bbox_index}|{label}",
                "label": label,
                "category_zh": cat_zh,
                "bbox_index": bbox_index,
                "integrity_score": round(integrity, 1),
                "base_kwh_h": round(base, 4),
                "degrade_factor": round(degrade, 3),
                "labels": labels,
                "values": values,
                "mean_kwh_h": round(mean_v, 4),
                "peak_kwh_h": round(max(values), 4) if values else 0.0,
                "min_kwh_h": round(min(values), 4) if values else 0.0,
            }
        )

    agg_values = [round(x, 4) for x in agg]
    agg_mean = round(sum(agg_values) / len(agg_values), 4) if agg_values else None
    return {
        "horizon_hours": horizon_hours,
        "model": "appliance_load_profile",
        "scope": "per_detection",
        "appliances": out_items,
        "aggregated": {
            "labels": labels,
            "values": agg_values,
            "mean_kwh_h": agg_mean,
            "peak_kwh_h": round(max(agg_values), 4) if agg_values else None,
            "min_kwh_h": round(min(agg_values), 4) if agg_values else None,
        },
    }


def save_upload_temp(data: bytes, original_name: str | None) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = ""
    if original_name and "." in original_name:
        ext = "." + original_name.rsplit(".", 1)[-1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        ext = ".jpg"
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)
    return path


def _legend() -> list[dict[str, str]]:
    return [
        {"status": "high", "color": "red", "meaning": "高耗能/异常"},
        {"status": "warning", "color": "yellow", "meaning": "预警"},
        {"status": "normal", "color": "green", "meaning": "正常/节能"},
    ]
