"""高德 Web 服务：逆地理编码（Key 仅存后端）。"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

AMAP_REGEO_URL = "https://restapi.amap.com/v3/geocode/regeo"


def _pick_city(comp: dict[str, Any]) -> str:
    city = comp.get("city")
    if isinstance(city, list):
        return str(city[0] or comp.get("province") or "")
    return str(city or comp.get("province") or "")


def _pick_address_detail(comp: dict[str, Any], formatted: str) -> str:
    sn = comp.get("streetNumber") or {}
    parts = [
        comp.get("township"),
        comp.get("street"),
        sn.get("street") if isinstance(sn, dict) else None,
        sn.get("number") if isinstance(sn, dict) else None,
    ]
    cleaned = [str(p).strip() for p in parts if p and str(p).strip()]
    if cleaned:
        return "".join(cleaned)
    if formatted:
        rest = formatted
        for seg in [comp.get("province"), _pick_city(comp), comp.get("district")]:
            seg_s = str(seg or "")
            if seg_s and rest.startswith(seg_s):
                rest = rest[len(seg_s) :]
        rest = rest.strip()
        return rest or formatted
    return ""


def is_configured() -> bool:
    return bool(settings.amap_web_key)


def reverse_geocode(lng: float, lat: float) -> dict[str, str]:
    key = settings.amap_web_key
    if not key:
        raise ValueError("未配置高德 Key，请在 backend/.env 中设置 AMAP_WEB_KEY")

    params = {
        "key": key,
        "location": f"{lng},{lat}",
        "extensions": "base",
        "output": "JSON",
    }
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(AMAP_REGEO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        raise ValueError(f"高德服务请求失败：{e}") from e

    if str(data.get("status")) != "1":
        raise ValueError(str(data.get("info") or "高德逆地理编码失败"))

    regeo = data.get("regeocode") or {}
    comp = regeo.get("addressComponent") or {}
    formatted = str(regeo.get("formatted_address") or "")
    return {
        "province": str(comp.get("province") or ""),
        "city": _pick_city(comp),
        "district": str(comp.get("district") or ""),
        "addressDetail": _pick_address_detail(comp, formatted),
    }
