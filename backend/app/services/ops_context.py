"""
智慧运维：为 RAG/LLM 拼装「数据字典」检索摘要与「能耗/异常」实时数据片段。
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.dataset_paths import data_dictionary_csv_path
from app.services.sikong_qa import expand_query_terms


@lru_cache(maxsize=1)
def _load_dictionary_rows() -> tuple[dict[str, str], ...]:
    path: Path = data_dictionary_csv_path()
    if not path.is_file():
        return tuple()
    rows: list[dict[str, str]] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return tuple(rows)


def search_data_dictionary(query: str, limit: int = 12) -> dict[str, Any]:
    """按关键词在数据字典各行文本中匹配。"""
    q = (query or "").strip()
    if not q:
        return {"ready": False, "count": 0, "items": [], "message": "空查询"}

    rows = _load_dictionary_rows()
    if not rows:
        return {
            "ready": False,
            "count": 0,
            "items": [],
            "message": f"未找到数据字典文件：{data_dictionary_csv_path()}",
        }

    terms = expand_query_terms(q)
    scored: list[tuple[int, dict[str, str]]] = []
    q_lower = q.lower()

    for r in rows:
        blob = "\n".join(f"{k}:{v}" for k, v in r.items()).lower()
        score = 0
        if q_lower in blob:
            score += 8
        for t in terms:
            tl = t.lower()
            if len(tl) >= 2 and tl in blob:
                score += 1
        if score > 0:
            scored.append((score, dict(r)))

    scored.sort(key=lambda x: -x[0])
    top = scored[:limit]
    return {
        "ready": True,
        "count": len(top),
        "items": [r for _, r in top],
    }


def clear_dictionary_cache() -> None:
    _load_dictionary_rows.cache_clear()


_OPS_TRIGGER = re.compile(
    r"能耗|用电|电耗|kwh|千瓦时|异常|波动|尖峰|建筑|楼栋|运行|状态|设备|"
    r"cop|冷量|统计|对标|对标|告警|故障|负荷|功率",
    re.I,
)


def ops_data_bundle(query: str, building_id: str | None = None) -> dict[str, Any]:
    """
    当问题疑似与运维数据相关时，注入时段汇总与异常检测摘要（全库或指定建筑）。
    """
    q = (query or "").strip()
    if not q or not _OPS_TRIGGER.search(q):
        return {"included": False, "summary_text": "", "raw": {}}

    from app.services import stats_service

    ps = stats_service.period_summary(building_id, None, None)
    aa = stats_service.anomaly_analysis(building_id, None, None, z_threshold=3.0)

    raw = {"period": ps, "anomalies": aa}
    lines = [
        "【实时数据摘要（演示数据集，非实时接入）】",
        f"- 记录行数：{ps.get('rows', 0)}；时间范围：{ps.get('time_range', {})}",
        f"- 市电累计 kWh（片段内）：{ps.get('sums', {}).get('electricity_kwh')}",
        f"- 异常小时（|z|>3）：{aa.get('anomaly_hours')} / {aa.get('total_hours')}，占比 {float(aa.get('ratio') or 0):.2%}",
    ]
    samples = aa.get("samples") or []
    if samples:
        lines.append("- 异常样例（节选）：")
        for s in samples[:5]:
            lines.append(
                f"  · {s.get('building_id')} @ {s.get('monitor_time')} 用电 {s.get('electricity_kwh')} kWh"
            )

    return {
        "included": True,
        "summary_text": "\n".join(lines),
        "raw": raw,
    }


def format_dictionary_for_prompt(items: list[dict[str, str]], max_chars: int = 3500) -> str:
    if not items:
        return ""
    parts: list[str] = ["【数据字典（字段说明节选）】"]
    n = 0
    for i, row in enumerate(items, 1):
        line = f"{i}. " + " | ".join(f"{k}={v}" for k, v in row.items() if v)[:500]
        parts.append(line)
        n += len(line)
        if n >= max_chars:
            parts.append("…（已截断）")
            break
    return "\n".join(parts)
