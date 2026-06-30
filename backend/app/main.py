from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.logging_config import configure_logging
from app.middleware.auth_gate import auth_gate_middleware
from app.middleware.request_log import request_log_middleware
from app.routers import admin, assistant, auth, chatchat_proxy, energy, incidents, kb, mcp_manifest, meta, sikong, stats, v2, wo_compat, work_orders
from app.services import energy_sync


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    configure_logging()
    await energy_sync.start_sync_loop()
    yield
    await energy_sync.stop_sync_loop()


app = FastAPI(
    title="建筑能源智能管理 API",
    description="赛题 A08：能耗数据查询统计（时段汇总/COP 演示/异常分析）、报表导出、规范 PDF 知识库、司空语料、数据字典与运维数据摘要、可选 OpenAI 兼容 LLM 的智慧运维问答（/assistant/rag-answer）、MCP 工具清单。",
    version="0.2.3",
    lifespan=_lifespan,
)

_cors_allow_all = "*" in settings.cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=not _cors_allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(auth_gate_middleware)
app.middleware("http")(request_log_middleware)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(energy.router, prefix=settings.api_prefix)
app.include_router(stats.router, prefix=settings.api_prefix)
app.include_router(kb.router, prefix=settings.api_prefix)
app.include_router(meta.router, prefix=settings.api_prefix)
app.include_router(sikong.router, prefix=settings.api_prefix)
app.include_router(assistant.router, prefix=settings.api_prefix)
app.include_router(chatchat_proxy.router, prefix=settings.api_prefix)
app.include_router(mcp_manifest.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(incidents.router, prefix=settings.api_prefix)
app.include_router(work_orders.router, prefix=settings.api_prefix)
app.include_router(work_orders.technicians_router, prefix=settings.api_prefix)
app.include_router(wo_compat.router, prefix=settings.api_prefix)
app.include_router(v2.router, prefix=settings.api_prefix)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Not Found",
                "path": request.url.path,
                "hint": "路径需带 /api 前缀（例：/api/energy/buildings）；访问 GET /api 查看端点列表；交互文档 /docs",
            },
        )
    return await http_exception_handler(request, exc)


@app.get(f"{settings.api_prefix}", tags=["discovery"])
@app.get(f"{settings.api_prefix}/", tags=["discovery"])
def api_discovery() -> dict[str, Any]:
    """避免浏览器打开 /api 时出现裸 Not Found；并列出常用路径。"""
    p = settings.api_prefix
    return {
        "message": "建筑能源 API",
        "version": "0.2.3",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "examples": {
            "buildings": f"{p}/energy/buildings",
            "energy_records": f"{p}/energy/records?limit=10",
            "stats_period": f"{p}/stats/period",
            "stats_timeseries": f"{p}/stats/timeseries?building_id=Bobcat_education_Alissa&metric=electricity_kwh",
            "stats_benchmark": f"{p}/stats/benchmark/scoreboard?top_n=10",
            "stats_metrics_catalog": f"{p}/stats/metrics-catalog",
            "kb_search": f"{p}/kb/search?q=节能",
            "sikong_search": f"{p}/sikong/search?q=热工",
            "rag_answer": f"{p}/assistant/rag-answer (POST JSON: query)",
            "chatchat_status": f"{p}/chatchat/status",
            "chatchat_kb_chat": f"{p}/chatchat/kb-chat (POST JSON: query, kb_name, …转发至队友 Chatchat)",
            "incidents": f"{p}/incidents",
            "incidents_summary": f"{p}/incidents/summary",
            "v2_vision_analyze": f"{p}/v2/vision/analyze (POST JSON: filename)",
            "v2_vision_upload": f"{p}/v2/vision/upload (POST multipart: file; query: prompt, conf, iou, imgsz optional)",
            "v2_twin_scene": f"{p}/v2/twin/scene",
            "v2_ops_suggestions": f"{p}/v2/ops/suggestions",
            "v2_forecast": f"{p}/v2/forecast/energy?horizon_hours=24",
            "v2_reports": f"{p}/v2/reports/operations?file_format=word",
            "mcp_tools": f"{p}/mcp/tools",
        },
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "auth_enabled": str(settings.auth_enabled).lower()}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "建筑能源 API",
        "docs": "/docs",
        "api": settings.api_prefix,
    }
