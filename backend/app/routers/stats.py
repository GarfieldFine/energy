from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services import report_export, stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/period")
def period_summary(
    building_id: str | None = Query(None),
    time_from: str | None = Query(None),
    time_to: str | None = Query(None),
) -> dict[str, Any]:
    return stats_service.period_summary(building_id, time_from, time_to)


@router.get("/anomalies")
def anomalies(
    building_id: str | None = Query(None),
    time_from: str | None = Query(None),
    time_to: str | None = Query(None),
    z_threshold: float = Query(3.0, ge=0.5, le=10.0),
) -> dict[str, Any]:
    return stats_service.anomaly_analysis(building_id, time_from, time_to, z_threshold)


@router.get("/cop-proxy")
def cop_proxy(
    building_id: str | None = Query(None),
    time_from: str | None = Query(None),
    time_to: str | None = Query(None),
) -> dict[str, Any]:
    return stats_service.cop_proxy_analysis(building_id, time_from, time_to)


@router.get("/timeseries")
def timeseries(
    building_id: str | None = Query(None, description="建筑 ID；省略则按时刻汇总全部建筑"),
    metric: str = Query("electricity_kwh", description="监测指标字段名"),
    time_from: str | None = Query(None),
    time_to: str | None = Query(None),
    limit: int = Query(2000, ge=10, le=10000),
) -> dict[str, Any]:
    """赛题：可视化图表数据源（折线/柱状图）。"""
    return stats_service.timeseries_for_chart(building_id, metric, time_from, time_to, limit)


@router.get("/metrics-catalog")
def metrics_catalog() -> dict[str, Any]:
    """指标中心：统一字段中文名、单位与推荐图表。"""
    return stats_service.metrics_catalog()


@router.get("/benchmark/scoreboard")
def benchmark_scoreboard(
    time_from: str | None = Query(None),
    time_to: str | None = Query(None),
    top_n: int = Query(20, ge=3, le=200),
) -> dict[str, Any]:
    """建筑对标排行榜：总电耗/夜间基荷占比/峰谷比综合评分。"""
    return stats_service.benchmark_scoreboard(time_from=time_from, time_to=time_to, top_n=top_n)


@router.get("/export/csv")
def export_csv(
    building_id: str | None = Query(None),
    time_from: str | None = Query(None),
    time_to: str | None = Query(None),
) -> StreamingResponse:
    """赛题：导出统计/明细报表（CSV）。"""
    name, raw = report_export.period_summary_csv(building_id, time_from, time_to)
    return StreamingResponse(
        iter([raw]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
