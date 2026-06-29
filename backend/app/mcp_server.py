"""
Strict MCP (Model Context Protocol) server over stdio.

This process is separate from the FastAPI web server. It exposes the same
capabilities as MCP tools for an agent/desktop client to call.

Run:
  python -m app.mcp_server
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.services import kb_search, rag_answer, sikong_qa, stats_service
from app.services import incidents_store, v2_service
from app.services.energy_store import list_buildings, query_energy
from app.services.report_export import period_summary_csv

mcp = FastMCP(name="building-energy-demo")


@mcp.tool()
def energy_list_buildings() -> dict[str, Any]:
    """List building metadata rows."""
    return {"items": list_buildings()}


@mcp.tool()
def energy_query_records(
    building_id: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Query hourly energy records by building/time window."""
    items = query_energy(building_id=building_id, time_from=time_from, time_to=time_to, limit=limit)
    return {"count": len(items), "items": items}


@mcp.tool()
def stats_period_summary(
    building_id: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
) -> dict[str, Any]:
    """Period summary statistics (sums/means)."""
    return stats_service.period_summary(building_id, time_from, time_to)


@mcp.tool()
def stats_anomaly_zscore(
    building_id: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    z_threshold: float = 3.0,
) -> dict[str, Any]:
    """Electricity anomaly detection using z-score (demo)."""
    return stats_service.anomaly_analysis(building_id, time_from, time_to, z_threshold)


@mcp.tool()
def stats_cop_proxy(
    building_id: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
) -> dict[str, Any]:
    """COP proxy demo: chilledwater_kwh_eq / electricity_kwh hourly ratio stats."""
    return stats_service.cop_proxy_analysis(building_id, time_from, time_to)


@mcp.tool()
def stats_timeseries_chart(
    building_id: str,
    metric: str = "electricity_kwh",
    time_from: str | None = None,
    time_to: str | None = None,
    limit: int = 2000,
) -> dict[str, Any]:
    """Time series for charts (labels+values)."""
    return stats_service.timeseries_for_chart(building_id, metric, time_from, time_to, limit)


@mcp.tool()
def stats_metrics_catalog() -> dict[str, Any]:
    """Metrics catalog with labels/units/chart hints."""
    return stats_service.metrics_catalog()


@mcp.tool()
def stats_benchmark_scoreboard(
    time_from: str | None = None,
    time_to: str | None = None,
    top_n: int = 20,
) -> dict[str, Any]:
    """Building benchmark scoreboard for demo dashboard."""
    return stats_service.benchmark_scoreboard(time_from=time_from, time_to=time_to, top_n=top_n)


@mcp.tool()
def export_energy_csv(
    building_id: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
) -> dict[str, Any]:
    """Export hourly detail CSV (UTF-8 with BOM) as text payload."""
    name, raw = period_summary_csv(building_id, time_from, time_to)
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode("utf-8", errors="replace")
    return {"filename": name, "csv": text}


@mcp.tool()
def kb_status() -> dict[str, Any]:
    """Knowledge base index readiness."""
    return {"index_ready": kb_search.is_index_ready()}


@mcp.tool()
def kb_search_pdf(q: str, limit: int = 15) -> dict[str, Any]:
    """Full-text search over indexed PDF knowledge base."""
    return kb_search.search_kb(q, limit=limit)


@mcp.tool()
def sikong_status() -> dict[str, Any]:
    """Sikong dataset readiness and row count."""
    return {"ready": sikong_qa.is_ready(), "rows": sikong_qa.count_rows()}


@mcp.tool()
def sikong_search_qa(q: str, limit: int = 20) -> dict[str, Any]:
    """Keyword search over Sikong text2text Q/A jsonl."""
    return sikong_qa.search_sikong(q, limit=limit)


@mcp.tool()
def assistant_knowledge_merge(query: str, kb_pdf_limit: int = 8, sikong_limit: int = 5) -> dict[str, Any]:
    """Merge PDF KB + Sikong retrieval results for RAG context."""
    pdf = kb_search.search_kb(query, limit=kb_pdf_limit)
    sik = sikong_qa.search_sikong(query, limit=sikong_limit)
    return {"query": query, "sources": {"pdf_kb": pdf, "sikong_qa": sik}}


@mcp.tool()
def assistant_rag_answer(query: str, kb_limit: int = 8, sikong_limit: int = 5) -> dict[str, Any]:
    """RAG-only answer assembled from retrieval evidence (no LLM)."""
    return rag_answer.unified_rag_answer(query, kb_limit=kb_limit, sikong_limit=sikong_limit)


@mcp.tool()
def incidents_list(status: str | None = None, limit: int = 100) -> dict[str, Any]:
    """List O&M incidents/work orders."""
    items = incidents_store.list_incidents(status=status, limit=limit)
    return {"count": len(items), "items": items}


@mcp.tool()
def incidents_summary() -> dict[str, Any]:
    """Counts by status, pending (open + in_progress), total."""
    return incidents_store.incident_summary()


@mcp.tool()
def incidents_create(
    title: str,
    building_id: str | None = None,
    severity: str = "medium",
    status: str = "open",
    detail: str | None = None,
) -> dict[str, Any]:
    """Create a new O&M incident."""
    item = incidents_store.create_incident(
        title=title,
        building_id=building_id,
        severity=severity,
        status=status,
        detail=detail,
    )
    return {"item": item}


@mcp.tool()
def v2_twin_scene(building_id: str | None = None) -> dict[str, Any]:
    """Digital twin scene mapping (rooms + status colors)."""
    return v2_service.twin_scene(building_id=building_id)


@mcp.tool()
def v2_ops_suggestions(building_id: str | None = None) -> dict[str, Any]:
    """Operations optimization suggestions from EWI/SU/DH style indicators."""
    return v2_service.ops_suggestions(building_id=building_id)


@mcp.tool()
def v2_forecast_energy(building_id: str | None = None, horizon_hours: int = 24) -> dict[str, Any]:
    """Hourly electricity forecast (Prophet when installed, else naive)."""
    return v2_service.forecast_energy(building_id=building_id, horizon_hours=horizon_hours)


@mcp.tool()
def incidents_patch(
    incident_id: int,
    title: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    """Update incident status/severity/detail."""
    item = incidents_store.update_incident(
        incident_id=incident_id,
        title=title,
        severity=severity,
        status=status,
        detail=detail,
    )
    return {"item": item}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

