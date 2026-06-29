"""
赛题要求「基于 MCP 协议」的数据接入与查询：此处提供与工具能力等价的 HTTP 清单，
便于智能体或自研 MCP Server 映射为 tools。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/tools")
def list_tools() -> dict[str, Any]:
    base = "/api"
    return {
        "protocol_note": "正式 MCP 需 stdio/SSE；此处为 REST 能力清单，便于映射为 MCP tools。",
        "server_name": "building-energy-demo",
        "tools": [
            {
                "name": "energy_list_buildings",
                "description": "列出建筑元数据",
                "method": "GET",
                "path": f"{base}/energy/buildings",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "energy_query_records",
                "description": "按建筑、时段查询小时级能耗记录",
                "method": "GET",
                "path": f"{base}/energy/records",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "building_id": {"type": "string"},
                        "time_from": {"type": "string"},
                        "time_to": {"type": "string"},
                        "limit": {"type": "integer", "default": 500},
                    },
                },
            },
            {
                "name": "stats_period_summary",
                "description": "时段汇总统计（赛题核心统计之一）",
                "method": "GET",
                "path": f"{base}/stats/period",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "building_id": {"type": "string"},
                        "time_from": {"type": "string"},
                        "time_to": {"type": "string"},
                    },
                },
            },
            {
                "name": "stats_cop_proxy",
                "description": "COP 相关：冷冻水冷量/市电小时比值（演示）",
                "method": "GET",
                "path": f"{base}/stats/cop-proxy",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "building_id": {"type": "string"},
                        "time_from": {"type": "string"},
                        "time_to": {"type": "string"},
                    },
                },
            },
            {
                "name": "stats_anomaly_zscore",
                "description": "用电异常分析（z-score，赛题核心统计之一）",
                "method": "GET",
                "path": f"{base}/stats/anomalies",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "building_id": {"type": "string"},
                        "time_from": {"type": "string"},
                        "time_to": {"type": "string"},
                        "z_threshold": {"type": "number", "default": 3.0},
                    },
                },
            },
            {
                "name": "stats_timeseries_chart",
                "description": "时序数据，供 ECharts 折线/柱状图",
                "method": "GET",
                "path": f"{base}/stats/timeseries",
                "parameters": {
                    "type": "object",
                    "required": ["building_id"],
                    "properties": {
                        "building_id": {"type": "string"},
                        "metric": {"type": "string", "default": "electricity_kwh"},
                        "time_from": {"type": "string"},
                        "time_to": {"type": "string"},
                        "limit": {"type": "integer", "default": 2000},
                    },
                },
            },
            {
                "name": "stats_metrics_catalog",
                "description": "指标中心：字段中文名、单位、推荐图表",
                "method": "GET",
                "path": f"{base}/stats/metrics-catalog",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "stats_benchmark_scoreboard",
                "description": "建筑对标排行榜（总电耗+夜间基荷占比+峰谷比综合分）",
                "method": "GET",
                "path": f"{base}/stats/benchmark/scoreboard",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "time_from": {"type": "string"},
                        "time_to": {"type": "string"},
                        "top_n": {"type": "integer", "default": 20},
                    },
                },
            },
            {
                "name": "export_energy_csv",
                "description": "导出时段明细 CSV 报表",
                "method": "GET",
                "path": f"{base}/stats/export/csv",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "building_id": {"type": "string"},
                        "time_from": {"type": "string"},
                        "time_to": {"type": "string"},
                    },
                },
            },
            {
                "name": "kb_search_pdf",
                "description": "规范 PDF 知识库全文检索",
                "method": "GET",
                "path": f"{base}/kb/search",
                "parameters": {
                    "type": "object",
                    "required": ["q"],
                    "properties": {"q": {"type": "string"}, "limit": {"type": "integer"}},
                },
            },
            {
                "name": "sikong_search_qa",
                "description": "司空大模型 text2text 语料检索",
                "method": "GET",
                "path": f"{base}/sikong/search",
                "parameters": {
                    "type": "object",
                    "required": ["q"],
                    "properties": {"q": {"type": "string"}, "limit": {"type": "integer"}},
                },
            },
            {
                "name": "assistant_knowledge_merge",
                "description": "合并 PDF 规范 + 司空语料原始检索结果（供二次封装）",
                "method": "POST",
                "path": f"{base}/assistant/knowledge-merge",
                "parameters": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string"},
                        "kb_pdf_limit": {"type": "integer"},
                        "sikong_limit": {"type": "integer"},
                    },
                },
            },
            {
                "name": "assistant_rag_answer",
                "description": "纯 RAG 运维问答：检索 PDF+司空语料并拼装回答（无 LLM）",
                "method": "POST",
                "path": f"{base}/assistant/rag-answer",
                "parameters": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string"},
                        "kb_limit": {"type": "integer"},
                        "sikong_limit": {"type": "integer"},
                    },
                },
            },
            {
                "name": "incidents_list",
                "description": "运维工单列表（异常闭环）",
                "method": "GET",
                "path": f"{base}/incidents",
                "parameters": {
                    "type": "object",
                    "properties": {"status": {"type": "string"}, "limit": {"type": "integer", "default": 100}},
                },
            },
            {
                "name": "incidents_summary",
                "description": "工单汇总：各状态计数、待处理数（open+in_progress）、总数",
                "method": "GET",
                "path": f"{base}/incidents/summary",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "incidents_create",
                "description": "创建运维工单（open/in_progress/resolved/closed）",
                "method": "POST",
                "path": f"{base}/incidents",
                "parameters": {
                    "type": "object",
                    "required": ["title"],
                    "properties": {
                        "title": {"type": "string"},
                        "building_id": {"type": "string"},
                        "severity": {"type": "string", "default": "medium"},
                        "status": {"type": "string", "default": "open"},
                        "detail": {"type": "string"},
                    },
                },
            },
            {
                "name": "incidents_patch",
                "description": "更新工单状态/级别/描述",
                "method": "PATCH",
                "path": f"{base}/incidents/{{incident_id}}",
                "parameters": {
                    "type": "object",
                    "required": ["incident_id"],
                    "properties": {
                        "incident_id": {"type": "integer"},
                        "title": {"type": "string"},
                        "severity": {"type": "string"},
                        "status": {"type": "string"},
                        "detail": {"type": "string"},
                    },
                },
            },
            {
                "name": "v2_twin_scene",
                "description": "V2 数字孪生场景：楼层房间与能耗状态",
                "method": "GET",
                "path": f"{base}/v2/twin/scene",
                "parameters": {"type": "object", "properties": {"building_id": {"type": "string"}}},
            },
            {
                "name": "v2_ops_suggestions",
                "description": "V2 运营优化建议（规则 + 指标）",
                "method": "GET",
                "path": f"{base}/v2/ops/suggestions",
                "parameters": {"type": "object", "properties": {"building_id": {"type": "string"}}},
            },
            {
                "name": "v2_forecast_energy",
                "description": "V2 能耗预测（Prophet 或回退）",
                "method": "GET",
                "path": f"{base}/v2/forecast/energy",
                "parameters": {
                    "type": "object",
                    "properties": {"building_id": {"type": "string"}, "horizon_hours": {"type": "integer", "default": 24}},
                },
            },
        ],
    }
