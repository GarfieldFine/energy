"""智能派单推荐：职责链思路（服务区域匹配 → 负载均衡）。"""
from __future__ import annotations

from typing import Any

from app.services import technicians_store


def _region_matches(tech_region: str, location: str) -> bool:
    """维修员服务区域与工单地址匹配（支持省/市/区子串互含）。"""
    region = (tech_region or "").strip()
    loc = (location or "").strip()
    if not region or not loc:
        return False
    if region in loc or loc in region:
        return True
    for token in (region, loc):
        for part in ("省", "市", "区", "县"):
            idx = token.find(part)
            if idx > 0:
                name = token[: idx + 1]
                if name and name in (loc if token == region else region):
                    return True
    return False


def recommend_technicians(
    location: str = "",
    building_id: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    top: int = 3,
    mode: str = "chain",
) -> dict[str, Any]:
    loc = (location or building_id or "").strip()
    if not loc:
        loc = "未填写地址"

    active = technicians_store.list_technicians(active_only=True)
    if not active:
        mode_label = "区域优先策略" if mode == "strategy" else "职责链（区域→负载）"
        return {"mode": mode, "mode_label": mode_label, "summary": "暂无可用维修员", "items": []}

    strategy_mode = str(mode or "chain").lower() == "strategy"
    mode_label = "区域优先策略" if strategy_mode else "职责链（区域→负载）"
    min_load = min(int(t.get("load_count") or 0) for t in active)
    scored: list[tuple[int, dict[str, Any]]] = []

    for tech in active:
        score = 0
        reasons: list[str] = []
        region = str(tech.get("region") or "")
        load = int(tech.get("load_count") or 0)
        region_match = _region_matches(region, loc)

        if strategy_mode:
            if region_match:
                score += 55
                reasons.append(f"服务区域匹配（{region}）")
            elif region:
                score += 12
                reasons.append(f"可跨区支援（登记 {region}）")
        else:
            if region_match:
                score += 40
                reasons.append(f"服务区域匹配（{region}）")
            elif region:
                score += 10
                reasons.append(f"可跨区支援（登记 {region}）")

        if load == min_load:
            score += 25 if not strategy_mode else 20
            reasons.append(f"当前负载最低（{load}）")
        elif load <= min_load + 1:
            score += 12 if not strategy_mode else 10
            reasons.append(f"负载较低（{load}）")

        skill = str(tech.get("skill_level") or "MEDIUM").upper()
        if category == "HVAC" and skill in {"HIGH", "MEDIUM"}:
            score += 15
            reasons.append("技能与空调/能耗类工单匹配")
        if priority in {"HIGH", "URGENT"} and skill == "HIGH":
            score += 10
            reasons.append("适合高优先级工单")

        if strategy_mode and region_match:
            reasons.insert(0, "策略模式首选（区域优先+负载）")
        elif not strategy_mode and region_match and load == min_load:
            reasons.insert(0, "职责链首选（区域匹配→负载均衡）")

        if not reasons:
            reasons.append("综合评分推荐")

        scored.append(
            (
                score,
                {
                    "id": tech["id"],
                    "name": tech["name"],
                    "region": region,
                    "skill_level": tech.get("skill_level"),
                    "load_count": load,
                    "contact_phone": tech.get("contact_phone"),
                    "match_score": score,
                    "match_reasons": reasons,
                },
            )
        )

    scored.sort(key=lambda x: (-x[0], x[1]["load_count"], x[1]["name"]))
    items = []
    for rank, (_, item) in enumerate(scored[: max(1, min(top, len(scored)))], start=1):
        item["rank"] = rank
        items.append(item)

    first = items[0]["name"] if items else "—"
    prefix = "区域优先策略推荐 " if strategy_mode else "职责链推荐 "
    summary = f"{prefix}{first}；Top{len(items)} 按服务区域/负载/技能排序（仅建议，不自动派单）"
    return {
        "mode": "strategy" if strategy_mode else "chain",
        "mode_label": mode_label,
        "summary": summary,
        "location": loc,
        "items": items,
    }
