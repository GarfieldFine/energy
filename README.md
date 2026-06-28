Building Energy System

建筑能源智能管理与孪生视觉演示系统（FastAPI + Vue3 + Vite + YOLO12）

本项目面向“建筑能耗监测 + 智慧运维 + 孪生视觉”场景，提供完整的演示链路：  
数据查询与统计分析、视觉识别与 3D 建模、运营建议与预测、知识问答、报告导出。

文档目标是让用户在 5~15 分钟内完成：
1) 理解系统模块  
2) 启动前后端  
3) 完成联调与基础验证



目录

- [1. 项目简介](#1-项目简介)
- [2. 功能清单](#2-功能清单)
- [3. 技术架构概览](#3-技术架构概览)
- [4. 项目结构](#4-项目结构)
- [5. 环境要求](#5-环境要求)
- [6. 启动前必要配置](#6-启动前必要配置)
- [7. 本地开发启动](#7-本地开发启动)
- [8. 扩展能力启动](#8-扩展能力启动)
- [9. Docker 一键部署](#9-docker-一键部署)
- [10. API 与联调入口](#10-api-与联调入口)
- [11. 快速自检清单](#11-快速自检清单)
- [12. 常见问题排错](#12-常见问题排错)
- [13. 文档索引](#13-文档索引)
- [14. 生产化建议](#14-生产化建议)



1. 项目简介

Building Energy System 是一个面向建筑能源管理的工程化演示项目，结合时序能耗数据、视觉识别与知识问答，支持运维分析与展示。  
系统采用前后端分离架构：后端 FastAPI 提供 REST API 与业务服务，前端 Vue3 提供可视化页面与交互式孪生场景。

核心能力：
- 能耗数据查询与统计分析（period / timeseries / anomalies / cop）
- 孪生与视觉识别（图片上传、YOLO-World / YOLO12 检测、3D 建模）
- 运营建议与能耗预测（Prophet + naive fallback）
- 知识问答（PDF + 司空语料 + LLM）
- 报告导出（Word / PDF）
- MCP 工具映射（stdio）



2. 功能清单

2.1 数据分析
- 能耗记录查询：`GET /api/energy/records`
- 时段统计：`GET /api/stats/period`
- 时序曲线：`GET /api/stats/timeseries`
- 异常检测：`GET /api/stats/anomalies`
- COP 演示：`GET /api/stats/cop-proxy`
- CSV 导出：`GET /api/stats/export/csv`

2.2 孪生视觉
- 视觉占位分析：`POST /api/v2/vision/analyze`
- 图片上传识别（YOLO-World / YOLO12）：`POST /api/v2/vision/upload`
- 孪生场景数据：`GET /api/v2/twin/scene`

2.3 运营与预测
- 运营指标：`GET /api/v2/ops/indicators`
- 运营建议：`GET /api/v2/ops/suggestions`
- 能耗预测：`GET /api/v2/forecast/energy`

2.4 知识问答
- 问答入口：`POST /api/assistant/rag-answer`
- LLM 状态：`GET /api/assistant/llm-status`
- 索引重建：`POST /api/admin/kb/reindex`

2.5 报告与集成
- 报告导出：`GET /api/v2/reports/{operations|esg}`
- MCP 工具：`python -m app.mcp_server`（stdio）



3. 技术架构概览

- 前端层（Vue3 + Vite）
  - `frontend/src/views/*`：业务页面（含孪生与视觉）
  - `frontend/src/api/index.js`：接口封装层
- API 路由层（FastAPI Routers）
  - `backend/app/routers/*`：统一路由入口，参数校验与响应组织
- 服务层（Services）
  - `backend/app/services/*`：核心业务逻辑（预测、建议、视觉、报告）
- 数据与知识层
  - CSV 数据源、PDF 知识库索引、司空语料、LLM

调用链示例：  
`TwinView.vue -> src/api/index.js -> /api/v2/* Router -> v2_service.py`，再到数据、模型与规则输出



4. 项目结构

```text
building_energy_system/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ routers/
│  │  └─ services/
│  ├─ scripts/
│  ├─ requirements.txt
│  ├─ requirements-v2-vision.txt
│  ├─ .env.example
│  └─ .env.docker.example
├─ frontend/
│  ├─ src/views/
│  ├─ src/api/
│  └─ vite.config.js
├─ docs/
│  ├─ TECHNICAL.md
│  ├─ API_FRONTEND.md
│  └─ USER_MANUAL.md
├─ docker-compose.yml
└─ START.txt
```



5. 环境要求

- Python 3.10+（基线 3.11）
- Node.js 18+（LTS）
- npm 9+
- Docker / Docker Compose

默认端口：
- 后端：`8765`
- 前端开发：`5173`
- Docker 前端：`8080`



6. 启动前必要配置

步骤 1：复制 `.env`

Windows：
```bash
cd backend
copy .env.example .env
```

macOS / Linux：
```bash
cd backend
cp .env.example .env
```

预期结果：`backend/.env` 文件存在。

步骤 2：配置数据路径

在 `backend/.env` 中至少配置：

```env
ENERGY_CSV=d:/BDG数据集/bdg_cleaned_output/building_energy_hourly.csv
METADATA_CSV=d:/BDG数据集/bdg_cleaned_output/metadata_subset.csv
DATA_DICTIONARY_CSV=d:/BDG数据集/building_energy_system/backend/data/imported/data_dictionary.csv
```

预期结果：后端能读取能耗与元数据，统计接口可返回有效数据。

步骤 3：配置知识库

```env
KB_ROOT=d:/BDG数据集/building_energy_system/kb_documents
KB_INDEX_DB=d:/BDG数据集/building_energy_system/backend/data/kb_index.sqlite
SIKONG_JSONL=d:/BDG数据集/sft_merged/sikong_sft_all.jsonl
```

步骤 4：配置 LLM

```env
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your_key
LLM_MODEL=qwen-turbo
LLM_TIMEOUT_SEC=120
```

步骤 5：配置视觉模型参数

```env
YOLO_WORLD_MODEL=yolov8x-worldv2.pt
YOLO_WORLD_IMGSZ=1280
YOLO_WORLD_IOU=0.42
YOLO_WORLD_MAX_DET=250
YOLO12_MODEL=yolo12x.pt
YOLO12_IMGSZ=1280
YOLO12_IOU=0.45
YOLO12_MAX_DET=250
```



7. 本地开发启动

7.1 启动后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
```

预期结果：
- 打开 `http://127.0.0.1:8765/docs` 可见 Swagger UI
- 打开 `http://127.0.0.1:8765/openapi.json` 返回 JSON

7.2 启动前端

```bash
cd frontend
npm install
npm run dev
```

预期结果：浏览器可访问 Vite 输出地址（通常 `http://127.0.0.1:5173`）。



8. 扩展能力启动

8.1 视觉依赖（YOLO-World / YOLO12）

```bash
cd backend
pip install -r requirements-v2-vision.txt
```

8.2 知识库索引（PDF 变更后）

```bash
cd backend
python scripts/ingest_kb.py
```



9. Docker 一键部署

步骤 1：准备 `.env`

Windows：
```bash
cd backend
copy .env.docker.example .env
```

macOS / Linux：
```bash
cd backend
cp .env.docker.example .env
```

并将数据放入 `backend/data/` 对应目录。

步骤 2：启动服务

在项目根目录执行：

```bash
docker compose up --build -d
```

预期结果：
- 前端：<http://localhost:8080>
- 后端文档：<http://127.0.0.1:8765/docs>



10. API 与联调入口

- API 文档：`/docs`
- OpenAPI 契约：`/openapi.json`

关键接口示例：
- `GET /api/v2/forecast/energy`
- `GET /api/v2/ops/suggestions`
- `POST /api/v2/vision/upload`（multipart 上传图片，支持 `mode=world|yolo12`）
- `POST /api/v2/vision/analyze`
- `GET /api/v2/twin/scene`
- `POST /api/assistant/rag-answer`

10.1 孪生与视觉标准操作流程

- 适用角色：运维工程师、空间管理人员、展示人员
- 输入条件：室内图片（上传）、识别参数（可选，支持 YOLO-World / YOLO12 双模型）
- 输出结果：识别结果、3D 建模预览、建模后运营建议

操作步骤：
1) 打开“孪生与视觉”页面
2) 上传室内图片
3) 选择识别模型：YOLO-World（开放词汇）或 YOLO12（封闭词汇）
4) 设置置信度、分辨率等参数
5) 执行识别并查看目标结果
6) 查看自动生成的 3D 建模预览
7) 查看“建模后运营建议”（视觉 + 能耗联动），并结合电器完好度/破损度结果判断巡检优先级  
   说明：破损度属于图像启发式评估，用于排序与提示，不替代现场电气检测结论。

成功判定：
- 图片识别成功
- 3D 模型可交互
- 建议表可显示

异常处理：
- 识别失败：更换清晰图片、调整模型与置信度；设备类目标可优先尝试 YOLO12
- 模型为空：检查识别结果中是否存在有效目标框
- 建议缺失：确认已完成识别；如需建筑级能耗建议，选择关联建筑后再查看



11. 快速自检清单

启动后按顺序检查：

1) 后端健康：`/docs` 与 `/openapi.json` 均可访问  
2) 前端可用：页面正常打开，无全局 404  
3) 烟雾测试：
   - `GET /api/v2/forecast/energy` 返回预测数组
   - `GET /api/v2/ops/suggestions` 返回建议列表
   - 上传图片到 `/api/v2/vision/upload` 返回 `yolo` 字段（分别测试 `mode=world` 与 `mode=yolo12`）  
4) 扩展检查：
   - `/api/assistant/llm-status` 显示 LLM 状态
   - 报告导出接口可下载文件



12. 常见问题排错

12.1 现象：返回 `{"detail":"Not Found"}`
- 原因：后端未启动，或前端代理目标端口不一致
- 处理：
  1. 访问 `http://127.0.0.1:<port>/docs`
  2. 检查前端代理配置与后端端口是否一致

12.2 现象：端口被占用
- 原因：本机已有进程占用 8765
- 处理：换端口启动
  ```bash
  python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 18888
  ```

12.3 现象：YOLO 接口无结果或报错
- 原因：视觉依赖未安装、权重不可达、运行资源不足
- 处理：
  1. 安装 `requirements-v2-vision.txt`
  2. 检查模型路径与网络下载（`YOLO_WORLD_MODEL` / `YOLO12_MODEL`）
  3. 查看返回中的 `yolo.hint` / `yolo.error`

12.4 现象：LLM 调用失败
- 原因：`LLM_API_BASE/KEY/MODEL` 配置错误
- 处理：
  1. 检查 `.env` 变量值
  2. 调用 `GET /api/assistant/llm-status` 诊断



13. 文档索引

- 技术说明：[`docs/TECHNICAL.md`](docs/TECHNICAL.md)
- 前端 API：[`docs/API_FRONTEND.md`](docs/API_FRONTEND.md)
- 用户手册：[`docs/USER_MANUAL.md`](docs/USER_MANUAL.md)
- 启动说明：[`START.txt`](START.txt)



