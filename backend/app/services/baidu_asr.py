"""百度智能云短语音识别（REST API）。"""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from app.config import settings

_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
_ASR_URL = "https://vop.baidu.com/server_api"

_token_cache: dict[str, Any] = {"token": "", "expires_at": 0.0}


def baidu_asr_configured() -> bool:
    return bool(settings.baidu_speech_api_key and settings.baidu_speech_secret_key)


def _get_access_token() -> str:
    if not baidu_asr_configured():
        raise RuntimeError("未配置百度语音：请在 backend/.env 设置 BAIDU_SPEECH_API_KEY 与 BAIDU_SPEECH_SECRET_KEY")

    now = time.time()
    cached = _token_cache.get("token") or ""
    expires_at = float(_token_cache.get("expires_at") or 0)
    if cached and now < expires_at - 60:
        return cached

    params = {
        "grant_type": "client_credentials",
        "client_id": settings.baidu_speech_api_key,
        "client_secret": settings.baidu_speech_secret_key,
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(_TOKEN_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    if "access_token" not in data:
        err = data.get("error_description") or data.get("error") or str(data)
        raise RuntimeError(f"百度语音获取 access_token 失败：{err}")

    token = str(data["access_token"])
    expires_in = int(data.get("expires_in") or 2592000)
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + expires_in
    return token


def recognize_speech(
    audio_bytes: bytes,
    *,
    fmt: str = "wav",
    rate: int = 16000,
    dev_pid: int | None = None,
) -> dict[str, Any]:
    """
    调用百度短语音识别，返回 { text, raw }。
    fmt: pcm / wav / amr / m4a；rate 须与音频采样率一致（常用 16000）。
    """
    if not audio_bytes:
        raise ValueError("音频为空")
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise ValueError("音频超过 10MB 上限")

    token = _get_access_token()
    pid = dev_pid if dev_pid is not None else settings.baidu_speech_dev_pid
    payload: dict[str, Any] = {
        "format": fmt,
        "rate": rate,
        "channel": 1,
        "cuid": settings.baidu_speech_app_id or "building_energy_asr",
        "token": token,
        "speech": base64.b64encode(audio_bytes).decode("ascii"),
        "len": len(audio_bytes),
        "dev_pid": pid,
    }

    with httpx.Client(timeout=settings.baidu_speech_timeout_sec) as client:
        resp = client.post(_ASR_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    err_no = int(data.get("err_no", -1))
    if err_no != 0:
        err_msg = data.get("err_msg") or f"err_no={err_no}"
        raise RuntimeError(f"百度语音识别失败：{err_msg}")

    results = data.get("result") or []
    text = "".join(str(x) for x in results).strip()
    return {"text": text, "raw": data}
