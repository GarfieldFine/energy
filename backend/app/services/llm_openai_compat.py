"""
OpenAI 兼容 Chat Completions（适用于 Ollama / vLLM / 硅基流动 / 通义 OpenAI 模式等）。
无额外依赖：stdlib urllib。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.config import settings


def _format_llm_http_error(status: int, body: str) -> str:
    """解析 OpenAI/百炼等返回的 JSON，便于排查密钥、模型名、欠费等问题。"""
    body = (body or "").strip()
    hint = ""
    try:
        data = json.loads(body)
        err = data.get("error")
        if isinstance(err, dict):
            msg = (err.get("message") or err.get("msg") or "").strip()
            code = (err.get("code") or err.get("type") or "").strip()
            if msg:
                hint = msg
                if code:
                    hint = f"[{code}] {hint}"
        elif isinstance(err, str) and err:
            hint = err
        if not hint and data.get("message"):
            hint = str(data["message"])
    except json.JSONDecodeError:
        pass
    if not hint:
        hint = body[:600] if body else "(无响应体)"
    # 常见说明（百炼文档：仅需 API-KEY + model 参数，无需自建模型）
    extra = ""
    low = hint.lower()
    if status == 401 or "invalid" in low and "api" in low:
        extra = " 请核对百炼控制台的 API-KEY 是否完整、未过期，且复制时无多余空格。"
    elif status == 400 and ("model" in low or "not exist" in low or "invalid" in low):
        extra = " 请核对 LLM_MODEL 是否与百炼「模型列表」中名称一致（如 qwen-turbo、qwen-plus）；一般无需单独部署模型。"
    elif "access" in low or "permission" in low or "denied" in low:
        extra = " 请在百炼控制台确认该账号已开通模型服务/未欠费。"
    return f"LLM HTTP {status}: {hint}{extra}"


def llm_configured() -> bool:
    base = (settings.llm_api_base or "").strip()
    return bool(base)


def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.35,
    max_tokens: int = 2048,
) -> tuple[str | None, str | None]:
    """
    返回 (assistant_content, error_message)。
    error_message 非空表示调用失败或响应异常。
    """
    if not llm_configured():
        return None, "LLM 未配置：请设置环境变量 LLM_API_BASE（及按需 LLM_API_KEY、LLM_MODEL）"

    base = settings.llm_api_base.strip().rstrip("/")
    key = (settings.llm_api_key or "").strip()
    if "dashscope" in base.lower() and not key:
        return (
            None,
            "使用阿里云百炼（通义千问）时请在 backend/.env 或环境变量中设置 LLM_API_KEY（百炼控制台创建的 API-KEY）。",
        )
    url = f"{base}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", f"Bearer {key}")

    try:
        with urllib.request.urlopen(req, timeout=settings.llm_timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(e)
        return None, _format_llm_http_error(e.code, detail)
    except Exception as e:
        return None, f"LLM 请求失败：{e}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, "LLM 响应非 JSON"

    try:
        choice = data["choices"][0]
        msg = choice.get("message") or {}
        content = (msg.get("content") or "").strip()
        if not content:
            return None, "LLM 返回空内容"
        return content, None
    except (KeyError, IndexError, TypeError):
        return None, f"LLM 响应结构异常：{raw[:400]}"
