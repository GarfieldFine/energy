# 智维衡碳 — Git 分批提交计划

**项目名称**：智维衡碳 — 建筑能源智能管理系统  
**团队**：李国豪、李金东、林佳星、刘嘉飞  
**依据文档**：`docs/智维衡碳-建筑能源智能管理系统-功能清单.xlsx`  
**编制说明**：远程仓库 [GarfieldFine/energy](https://github.com/GarfieldFine/energy) 已初始化；`main` 上已有 **阶段 1（06-28）** 与 **阶段 2A（06-29）** 两次提交。本计划按功能清单中的 **负责人 + 预计完成时间** 梳理四人分批次提交顺序与文件范围。

**当前 main 提交（截至 2026-06-29）**

| Commit | 说明 | 负责人 |
|--------|------|--------|
| `a72ce28` | 项目骨架、健康检查与能耗 CSV 存储 | 李国豪 · 06-28 |
| `a0c94a3` | JWT 鉴权、Admin 数据管理与知识库索引 | 李国豪 · 06-29 |

---

## 1. 总体原则

| 项 | 约定 |
|----|------|
| 主分支 | `main`，由 **李国豪** 负责合并 |
| 个人分支 | **李国豪** 使用 `lgh`；其余成员可用 `feat/ljd-0630` 等按日期命名 |
| 合并流程 | 个人分支开发 → `git merge lgh --no-ff` 进 `main` → `git push origin main` |
| 提交顺序 | **严格按日期**：后端 API → 前端页面 → 小程序 → 文档 |
| 提交作者 | `git config user.name` 与功能清单「负责人」一致 |
| 禁止提交 | 见根目录 `.gitignore`：`.env`、`*.csv`、`*.pt`、`node_modules/`、`frontend/dist/` 等 |
| 每阶段验收 | 后端 `uvicorn` 可启动；本阶段涉及页面可打开；无密钥泄漏 |

### 1.1 禁止提交清单（提交前必查）

```
backend/.env
backend/data/imported/
backend/data/uploads/
backend/*.sqlite
*.pt
*.csv
frontend/node_modules/
frontend/dist/
miniprogram/project.private.config.json
```

### 1.2 提交日期与清单对齐（可选）

若需 commit 时间与功能清单「预计完成时间」一致，可使用：

```bash
GIT_AUTHOR_DATE="2026-06-28 18:00:00" \
GIT_COMMITTER_DATE="2026-06-28 18:00:00" \
git commit -m "feat(backend): 项目骨架、健康检查与能耗 CSV 存储"
```

团队需统一是否采用；仅用于与清单时间对齐，不影响代码内容。

---

## 2. 四人职责与模块对照

| 成员 | 项目角色 | 主责模块 | 提交侧重目录 |
|------|----------|----------|--------------|
| **李国豪** | 项目负责人 | M1 数据底座、M6 工单后端、M12 系统管理、M10 部署/MCP | `backend/app/routers/{auth,energy,admin,incidents,meta,mcp_manifest}.py`、`energy_store`、`incidents_store`、`docker-compose.yml` |
| **李金东** | 技术负责人 | M2 统计、M5 RAG、M8 预测、M9 报告、技术文档 | `backend/app/routers/{stats,assistant,kb,sikong,v2}.py`、`services/{stats,rag,sikong,llm,v2}*`、`docs/API_FRONTEND.md` 等 |
| **林佳星** | 前端负责人 | M4/M6/M7/M11 前端 UI、小程序 | `frontend/src/views/`、`components/`、`composables/`、`miniprogram/` |
| **刘嘉飞** | 算法与测试 | M3/M5/M7 算法参数、RAG/异常/视觉评测 | 异常阈值、RAG/视觉 conf 调优、`scripts/loadtest/`、测试与评测文档 |

### 2.1 每人建议 commit 次数

| 成员 | 次数 | 日期分布 |
|------|:----:|----------|
| 李国豪 | 7～8 | 06-28 → … → 07-04 → **07-05 报单后端** |
| 李金东 | 5～6 | 06-29 → … → 07-04 |
| 林佳星 | 7～8 | 06-29 → … → 07-03 → **07-05 报单前端** → **07-06 能源分析导航** |
| 刘嘉飞 | 4～5 | 07-01 → … → 07-04 → **07-05 视觉阈值** |

---

## 3. 分阶段提交计划（9 个阶段）

---

### 阶段 1 · 2026-06-28

**负责人**：李国豪  
**清单条目（4 项）**

| 二级模块 | 功能点 | 说明 |
|----------|--------|------|
| 1.1 用户与权限管理 | 角色权限划分 | 预设四类角色；V1.0 POC 以菜单隔离为主 |
| 1.2 系统基础功能 | 健康检查 | GET /health 返回服务状态 |
| 2.1 能耗数据管理 | 建筑列表 | GET /api/buildings 或 energy 建筑接口 |
| 2.2 混合存储架构 | CSV 时序存储 | building_energy_hourly.csv 字段骨架 |

**提交文件**

```
.gitignore
README.md
START.txt
backend/requirements.txt
backend/app/__init__.py
backend/app/main.py
backend/app/config.py
backend/app/routers/__init__.py
backend/app/routers/meta.py
backend/app/routers/energy.py
backend/app/services/__init__.py
backend/app/services/energy_store.py
backend/app/services/dataset_paths.py
```

**提交说明**

```
feat(backend): 项目骨架、健康检查与能耗 CSV 存储
```

**验收**

- [ ] `GET /health` 返回 `status: ok`
- [ ] 能耗 CSV 路径可配置（环境变量或默认路径）
- [ ] 建筑列表接口可返回（可为空列表）

---

### 阶段 2 · 2026-06-29

本日 **3 人提交**，建议顺序：李国豪 → 李金东 → 林佳星。

#### 2A · 李国豪（9 项）

| 二级模块 | 功能点 |
|----------|--------|
| 1.1 用户与权限管理 | 账号管理、精细化权限控制 |
| 1.2 系统基础功能 | 文件与数据管理、知识库索引、系统参数配置 |
| 2.1 能耗数据管理 | 能耗明细查询、数据上传与重载、导入状态展示 |
| 2.2 混合存储架构 | SQLite 业务库 |

**提交文件**

```
backend/app/routers/auth.py
backend/app/middleware/auth_gate.py
backend/app/services/auth_service.py
backend/app/deps/auth.py
backend/app/routers/admin.py
backend/app/services/dataset_upload.py
backend/app/services/incidents_store.py
backend/app/routers/kb.py
backend/app/services/kb_search.py
backend/scripts/ingest_kb.py
backend/.env.example
```

**提交说明**

```
feat(backend): JWT 鉴权、Admin 数据管理与知识库索引
```

#### 2B · 李金东（1 项）

| 二级模块 | 功能点 |
|----------|--------|
| 2.2 混合存储架构 | JSONL 语料库 |

**提交文件**

```
backend/app/routers/sikong.py
backend/app/services/sikong_qa.py
backend/app/services/ops_context.py
```

**提交说明**

```
feat(rag): 司空 JSONL 语料检索基础
```

#### 2C · 林佳星（1 项）

| 二级模块 | 功能点 |
|----------|--------|
| 1.1 用户与权限管理 | 个人中心 |

**提交文件**

```
frontend/package.json
frontend/package-lock.json
frontend/vite.config.js
frontend/index.html
frontend/src/main.js
frontend/src/App.vue
frontend/src/views/LoginView.vue
frontend/src/stores/auth.js
frontend/src/router/index.js
frontend/src/api/client.js
frontend/src/api/index.js
frontend/src/utils/permissions.js
frontend/src/assets/
```

**提交说明**

```
feat(frontend): 登录页、JWT 状态与路由权限骨架
```

**验收**

- [ ] admin / energy / ops 演示账号可登录（见 START.txt）
- [ ] Admin 页可查看导入状态
- [ ] `ingest_kb.py` 可独立运行（需本地 PDF 目录）

#### 2D · 李国豪（06-29 增量 · 分支 `lgh`）

**说明**：阶段 2A 已合并进 `main` 后，同日继续补齐 **工单后端骨架**、**平台运维状态 API**、**能耗同步循环** 与 **部署配置**；在 `lgh` 分支提交后由李国豪 `--no-ff` 合并进 `main`。

| 二级模块 | 功能点 |
|----------|--------|
| 5.1 / 5.5 工单 | incidents API、状态机、兼容层、结构化地址字段 |
| 1.2 系统基础 | 平台运维 `/api/admin/status` 扩展、数据源连接摘要 |
| 2.1 能耗数据 | `energy_sync` 定时同步（`ENERGY_API_URL` 预留） |
| 9.x 部署 | MCP stdio/HTTP、Docker Compose |
| 1.1 用户与权限 | `users_store`、演示账号扩展 |

**提交文件**

```
START.txt
docker-compose.yml
backend/.env.example
backend/.env.docker.example
backend/Dockerfile
backend/.dockerignore
backend/app/config.py
backend/app/main.py
backend/app/mcp_server.py
backend/app/deps/__init__.py
backend/app/middleware/__init__.py
backend/app/middleware/auth_gate.py
backend/app/routers/admin.py
backend/app/routers/auth.py
backend/app/routers/incidents.py
backend/app/routers/mcp_manifest.py
backend/app/routers/work_orders.py
backend/app/routers/wo_compat.py
backend/app/services/auth_service.py
backend/app/services/incidents_store.py
backend/app/services/energy_sync.py
backend/app/services/users_store.py
backend/app/services/workorder_state_machine.py
backend/app/services/workorder_flow.py
backend/app/services/workorder_mapper.py
backend/app/services/dispatch_recommendation.py
backend/app/services/technicians_store.py
backend/app/services/technician_profile_requests_store.py
backend/app/services/amap_service.py
backend/scripts/mock_energy_api.py
backend/data/.gitkeep
docs/GIT_SUBMIT_PLAN.md
```

**依赖说明（同批合并）**：`main.py` 自阶段 2A 起已注册 `stats` / `sikong` / `assistant` / `v2` 等路由；本批 **`lgh` 合并时一并带上对应 router/service 文件**，保证 `uvicorn app.main:app` 可启动（李金东 / 刘嘉飞模块仍按后续阶段独立 commit 归属）。

**提交说明**

```
feat(backend): 工单后端、平台运维状态与能耗同步
```

**验收**

- [ ] `GET /api/admin/status` 返回 `sync` 与 `data_sources`
- [ ] 配置 `ENERGY_API_URL` 后显示 API 同步模式；未配置时为 file/import
- [ ] `GET /api/incidents` 与工单兼容 API 可访问
- [ ] `python -m app.mcp_server` 可列出工具；`docker compose config` 无语法错误

---

### 阶段 3 · 2026-06-30

本日 **3 人提交**，建议顺序：李金东 → 林佳星 → 李国豪。

#### 3A · 李金东（4 项）

| 二级模块 | 功能点 |
|----------|--------|
| 3.1 时段统计 | 时段汇总、时序曲线、COP 演示、CSV 导出 |

**提交文件**

```
backend/app/routers/stats.py
backend/app/services/stats_service.py
backend/app/services/report_export.py
```

**提交说明**

```
feat(stats): 时段汇总、时序曲线、COP 与 CSV 导出 API
```

#### 3B · 林佳星（5 项）

| 二级模块 | 功能点 |
|----------|--------|
| 1.2 系统基础功能 | 消息与提醒 |
| 3.3 能效对标 | 综合评分、排行榜展示 |
| 8.1 能源仪表盘 | 分项饼图 |
| 8.3 图表组件 | ECharts 封装 |

**提交文件**

```
frontend/src/components/AppChart.vue
frontend/src/components/AnimatedNumber.vue
frontend/src/composables/usePolling.js
frontend/src/composables/useCountUp.js
frontend/src/views/StatsView.vue
frontend/src/views/BenchmarkView.vue
frontend/src/views/DashboardView.vue
frontend/src/views/EnergyView.vue
frontend/src/utils/statsDisplay.js
frontend/src/utils/myemsCharts.js
frontend/src/styles/ems-theme.css
frontend/src/assets/main.css
frontend/src/assets/base.css
```

**提交说明**

```
feat(frontend): 仪表盘、统计页、对标页与 ECharts 封装
```

#### 3C · 李国豪（1 项）

| 二级模块 | 功能点 |
|----------|--------|
| 1.2 系统基础功能 | 日志管理 |

**提交文件**

```
backend/app/main.py          # 若含请求/异常日志中间件
```

**提交说明**

```
feat(backend): 基础请求与异常日志
```

**验收**

- [ ] StatsView 时段汇总与曲线可展示
- [ ] BenchmarkView 排行榜可展示
- [ ] DashboardView KPI 与饼图可展示

---

### 阶段 4 · 2026-07-01

本日 **3 人提交**，建议顺序：李金东 + 刘嘉飞 → 林佳星。

#### 4A · 李金东 + 刘嘉飞（4 项，可 1～2 条 commit）

| 负责人 | 二级模块 | 功能点 |
|--------|----------|--------|
| 李金东 | 3.2 异常检测 | Z-score 异常分析 |
| 刘嘉飞 | 3.2 异常检测 | 阈值可配置 |
| 刘嘉飞 | 4.1 知识检索 | PDF 规范检索、司空语料检索、数据字典注入 |

**提交文件**

```
backend/app/services/stats_service.py    # anomalies、z_threshold
backend/app/services/kb_search.py
backend/app/services/rag_answer.py       # 检索拼装基础（无 LLM 增强部分可后续）
```

**提交说明（李金东）**

```
feat(stats): Z-score 异常检测与 z_threshold 参数
```

**提交说明（刘嘉飞）**

```
feat(rag): PDF FTS 与司空语料检索、数据字典注入
```

#### 4B · 林佳星（6 项）

| 二级模块 | 功能点 |
|----------|--------|
| 3.2 异常检测 | 异常说明弹窗、异常占比提醒 |
| 3.3 能效对标 | 公式说明 |
| 8.1 能源仪表盘 | KPI 卡片、对标摘要 |
| 8.2 数据大屏 | 大屏布局 |

**提交文件**

```
frontend/src/views/StatsView.vue         # μ/σ 说明、异常列表
frontend/src/views/DashboardView.vue     # KPI、异常提醒
frontend/src/views/BenchmarkView.vue     # 公式说明抽屉
frontend/src/views/BigScreenView.vue
frontend/src/utils/workspaceNav.js
frontend/src/components/EmsHelpBtn.vue
```

**提交说明**

```
feat(frontend): 异常说明弹窗、仪表盘 KPI 与数据大屏
```

**验收**

- [ ] `GET /api/stats/anomalies?z_threshold=3` 可返回 ratio
- [ ] StatsView 可展示 μ、σ 说明
- [ ] BigScreenView 可打开（energy / ops 角色）

---

### 阶段 5 · 2026-07-02

本日 **3 人提交**，建议顺序：李国豪 → 刘嘉飞 → 林佳星。

#### 5A · 李国豪（6 项）

| 二级模块 | 功能点 |
|----------|--------|
| 5.1 工单 CRUD | 工单列表、详情、新建、状态更新、删除 |
| 5.2 工单统计 | 摘要统计 |

**提交文件**

```
backend/app/routers/incidents.py
```

**提交说明**

```
feat(incidents): 工单 CRUD 与摘要统计 API
```

#### 5B · 刘嘉飞（5 项）

| 二级模块 | 功能点 |
|----------|--------|
| 4.2 问答服务 | 双模式应答、 citations 溯源、建筑上下文 |
| 4.3 语音输入 | 语音转文字、语音填问 |

**提交文件**

```
backend/app/routers/assistant.py
backend/app/services/rag_answer.py
backend/app/services/llm_openai_compat.py
backend/app/services/baidu_asr.py
backend/app/routers/chatchat_proxy.py      # 若已配置 Chatchat 转发
frontend/src/composables/useVoiceInput.js
frontend/src/views/KnowledgeView.vue
```

**提交说明**

```
feat(assistant): RAG 双模式问答、citations 与语音输入
```

#### 5C · 林佳星（1 项）

| 二级模块 | 功能点 |
|----------|--------|
| 6.1 视觉识别 | 图片上传识别 |

**提交文件**

```
frontend/src/views/TwinView.vue            # 上传区与结果展示（3D 可下阶段补全）
frontend/src/utils/twinVisionMock.js
```

**提交说明**

```
feat(twin): 现场图片上传与识别结果展示
```

**验收**

- [ ] IncidentsView 列表/新建/受理/删除可用
- [ ] KnowledgeView 问答返回 citations
- [ ] TwinView 可上传图片并展示识别结果

---

### 阶段 6 · 2026-07-03

本日 **4 人提交**，清单条目最多（19 项），建议顺序：李金东 → 刘嘉飞 → 林佳星 → 李国豪。

#### 6A · 李金东（5 项）

| 二级模块 | 功能点 |
|----------|--------|
| 6.3 运营建议 | 建议列表 |
| 7.1 运营指标 | KPI 看板 |
| 7.2 能耗预测 | 48h 预测、horizon 可配 |
| 7.3 报告导出 | 运营报告、按建筑筛选 |

**提交文件**

```
backend/app/routers/v2.py
backend/app/services/v2_service.py
backend/app/services/v2_report_export.py
backend/requirements-v2-vision.txt
frontend/src/views/OperationsView.vue
```

**提交说明**

```
feat(v2): 运营指标、48h 预测、运营建议与报告导出
```

#### 6B · 刘嘉飞（2 项）

| 二级模块 | 功能点 |
|----------|--------|
| 6.1 视觉识别 | 电器健康评估、默认识别阈值 |

**提交文件**

```
backend/app/services/v2_service.py         # asset_health、conf/iou 默认值
```

**提交说明**

```
feat(vision): 电器健康评估与默认识别阈值调优
```

#### 6C · 林佳星（10 项）

| 二级模块 | 功能点 |
|----------|--------|
| 5.3 语音命令 | 命令解析、语音闭环、汉字数字 |
| 5.4 孪生联动 | 视觉预警草稿（VISION_DRAFT）、URL 深链 query.id |
| 6.1 视觉识别 | 图片上传识别（admin/ops/requester 权限） |
| 6.2 轻量 3D 孪生 | Three.js 场景、分析结果分 Tab、预警小弹窗、会话持久化 |
| 6.4 小程序巡检 | 选图上传、API 配置 |

**提交文件**

```
frontend/src/views/TwinView.vue              # Three.js 全量
frontend/src/stores/twinSession.js
frontend/src/utils/twinDamagedIncident.js
frontend/src/composables/useIncidentVoiceCommand.js
frontend/src/views/IncidentsView.vue         # 语音命令 UI
miniprogram/                                 # 整包（不含 project.private.config.json）
```

**提交说明**

```
feat(frontend+miniprogram): 孪生 3D、语音工单、自动建单与运维小程序
```

#### 6D · 李国豪（1 项）

| 二级模块 | 功能点 |
|----------|--------|
| 10.1 性能 | 缓存策略 |

**提交文件**

```
backend/app/services/energy_store.py       # LRU 缓存、reload 失效
backend/app/routers/admin.py               # POST /api/admin/reload
```

**提交说明**

```
perf(backend): energy_store LRU 缓存与 reload 失效
```

**验收**

- [ ] TwinView 3D 场景可交互，跳转工单后 session 可恢复
- [ ] 健康评分低于阈值可自动建单
- [ ] 小程序 ops 登录后可走工单/问答/现场三模块
- [ ] OperationsView 预测曲线可展示

---

### 阶段 7 · 2026-07-04

本日 **收尾集成**，建议顺序：李国豪 → 李金东 → 刘嘉飞 → 全体。

#### 7A · 李国豪（6 项）

| 二级模块 | 功能点 |
|----------|--------|
| 9.1 MCP HTTP | 工具清单 |
| 9.2 MCP stdio | stdio 服务 |
| 9.3 OpenAPI | 接口文档 |
| 9.4 部署 | Docker Compose、环境变量 |
| 10.2 安全 | 内网部署 |

**提交文件**

```
backend/app/routers/mcp_manifest.py
backend/app/mcp_server.py
backend/Dockerfile
backend/.dockerignore
backend/.env.docker.example
docker-compose.yml
```

**提交说明**

```
feat(deploy): MCP 集成、Docker Compose 与部署配置
```

#### 7B · 李金东（2 项）

| 二级模块 | 功能点 |
|----------|--------|
| 7.3 报告导出 | ESG 报告 |
| 10.3 可维护 | 开源文档 |

**提交文件**

```
backend/app/services/v2_report_export.py   # ESG 部分若与运营报告同文件可合并说明
docs/SOURCE_CODE_DOCUMENT.md
docs/API_FRONTEND.md
docs/需求文档V1.0.md
docs/智维衡碳-建筑能源智能管理系统-功能清单.xlsx
```

**提交说明**

```
docs: ESG 报告导出与技术文档收口
```

#### 7C · 刘嘉飞（1 项）

| 二级模块 | 功能点 |
|----------|--------|
| 10.4 测试 | 回归与评测 |

**提交文件**

```
docs/PROJECT_KICKOFF_BEFORE_START.md
scripts/loadtest/
docs/GIT_SUBMIT_PLAN.md
scripts/update_feature_list_v11.py
scripts/update_feature_list_v12.py
```

**提交说明**

```
test: 压测脚本、项目文档与 Git 提交计划
```

#### 7D · 全体（1 项）

| 二级模块 | 功能点 |
|----------|--------|
| 10.4 测试 | 全链路集成验收 |

**提交文件**

```
frontend/src/layouts/MainLayout.vue
frontend/src/styles/feishu-ui.css
frontend/src/components/EmsDrawer.vue
frontend/src/components/EmsDialog.vue
frontend/src/views/AdminView.vue
frontend/src/views/PricingView.vue
frontend/src/data/pricingPlans.js
README.md                                  # 最终版
```

**提交说明**

```
chore: V1.0 全链路 UI 集成与 README 收口
```

**验收**

- [ ] `docker compose up --build` 可启动
- [ ] `GET /api/mcp/tools` 返回工具清单
- [ ] 5 分钟 Demo 动线可走通（见 PROJECT_KICKOFF 答辩分工）
- [ ] 四人 commit 历史与功能清单日期、负责人一致

---

### 阶段 8 · 2026-07-05（V1.1 迭代）

**说明**：在 V1.0 集成基础上，补齐 **课设报单全流程**、**结构化地址与定位**、**视觉预警草稿**、**维修档案资质审批** 等清单新增条目（见功能清单 **5.5 课设报单流程**、**5.4 视觉预警草稿**、**10.4 体验**）。

本日 **3 人提交**，建议顺序：李国豪 → 林佳星 → 刘嘉飞。

#### 8A · 李国豪（6 项）

| 二级模块 | 功能点 |
|----------|--------|
| 5.5 课设报单流程 | 状态机与兼容 API、结构化报修地址、定位获取地址、草稿删除、维修员区域匹配、档案修改审批 |

**提交文件**

```
backend/app/services/workorder_state_machine.py
backend/app/services/workorder_flow.py
backend/app/services/workorder_mapper.py
backend/app/services/incidents_store.py          # province/city/district/address_detail
backend/app/routers/work_orders.py               # PATCH/submit-draft/delete、DraftPatchBody
backend/app/services/dispatch_recommendation.py  # 省市区子串匹配
backend/app/services/technicians_store.py        # 服务区域迁移为「广东省深圳市」等
backend/app/services/technician_profile_requests_store.py  # proof_attachment_filename
backend/app/services/amap_service.py             # 高德逆地理编码
backend/app/routers/wo_compat.py                 # /location/reverse、档案申请 attachmentFilename
backend/app/middleware/auth_gate.py              # requester 视觉 POST 权限
backend/.env.example                             # AMAP_WEB_KEY
```

**提交说明**

```
feat(work-orders): 课设报单状态机、结构化地址、高德定位代理与档案资质审批
```

#### 8B · 林佳星（5 项）

| 二级模块 | 功能点 |
|----------|--------|
| 5.4 孪生联动 | 视觉预警草稿、URL 深链 |
| 5.5 课设报单流程 | 报修员编辑工单、工单详情 Tab |
| 10.4 体验 | 报修员导航、登录页文案、顶栏提示样式 |
| 6.2 轻量 3D 孪生 | 分析结果分 Tab、预警小弹窗 |

**提交文件**

```
frontend/src/views/TwinView.vue                  # 小弹窗、移除待确认草稿按钮
frontend/src/utils/twinDamagedIncident.js        # VISION_DRAFT payload
frontend/src/components/WorkOrderDetailDrawer.vue # 详情/修改/轨迹 Tab
frontend/src/components/WorkOrderCreateForm.vue    # 省市区地址 + 定位按钮
frontend/src/components/AddressLocateButton.vue
frontend/src/utils/amapLocation.js               # 调用后端 /location/reverse
frontend/src/utils/workOrderConstants.js
frontend/src/utils/appMessage.js                 # 简约顶栏提示
frontend/src/composables/useToast.js
frontend/src/styles/ems-theme.css                # ElMessage 样式
frontend/src/views/ProfileView.vue               # 档案申请上传资质
frontend/src/views/TechniciansView.vue           # 审批查看附件
frontend/src/views/IncidentsView.vue
frontend/src/utils/permissions.js                # 报修员菜单
frontend/src/views/LoginView.vue
frontend/.env.example
```

**提交说明**

```
feat(frontend): 工单编辑 Tab、地址定位、视觉草稿 UI 与档案资质上传
```

#### 8C · 刘嘉飞（1 项）

| 二级模块 | 功能点 |
|----------|--------|
| 6.1 视觉识别 | 电器健康评估触发草稿（非直接建单） |

**提交文件**

```
backend/app/services/v2_service.py               # asset_health 阈值与破损等级（若本阶段有调参）
```

**提交说明**

```
feat(vision): 电器健康评估与视觉预警草稿阈值对齐
```

**验收**

- [ ] 报修员新建工单可「定位获取地址」（backend/.env 已配 AMAP_WEB_KEY）
- [ ] TwinView 识别破损电器 → 待二次确认工单 → 修改 Tab 提交 → 进入待接单
- [ ] 报修员在未接单前可修改自己的工单（独立「修改信息」Tab）
- [ ] 运维申请修改档案须上传附件；管理员可预览后审批
- [ ] 顶栏提示无感叹号图标，样式为简约卡片

---

### 阶段 9 · 2026-07-06（V1.2 导航与布局）

**说明**：在 V1.1 基础上，将能源相关 **5 个侧栏入口** 合并为 **「能源分析」** 单入口（四 Tab），优化预测页布局，并调整 **admin** 侧栏顺序。

本日 **1 人提交**（林佳星，可与 8B 合并为同一 PR）。

#### 9A · 林佳星（4 项）

| 二级模块 | 功能点 |
|----------|--------|
| 8.1 能源仪表盘 | 能源分析统一入口 |
| 8.1 能源仪表盘 | 分析子视图 |
| 7.2 能耗预测 | 预测一体页 |
| 10.4 体验 | 管理员菜单排序 |

**提交文件**

```
frontend/src/views/EnergyAnalyticsView.vue       # 能源分析壳层：标题 + 分段 Tab
frontend/src/views/AnalysisPanelView.vue         # 分析 Tab：统计 / 对标胶囊子导航
frontend/src/views/OperationsView.vue            # 预测 Tab：指标 + 预测同屏、顶栏筛选
frontend/src/views/DashboardView.vue             # 总览嵌入：隐藏重复大标题
frontend/src/views/EnergyView.vue
frontend/src/views/StatsView.vue
frontend/src/router/index.js                     # /analytics/* 子路由；旧路径 redirect
frontend/src/utils/permissions.js                # admin 菜单顺序；defaultHome → /analytics/overview
frontend/src/layouts/MainLayout.vue              # /analytics 高亮
frontend/src/stores/auth.js
scripts/update_feature_list_v12.py
docs/智维衡碳-建筑能源智能管理系统-功能清单.xlsx
docs/GIT_SUBMIT_PLAN.md
```

**提交说明**

```
feat(frontend): 能源分析四 Tab 合并导航、预测一体页与 admin 侧栏排序
```

**验收**

- [ ] admin / energy 侧栏仅 **1 项「能源分析」**（非原 5 项）
- [ ] Tab：**总览 / 明细 / 分析 / 预测** 可切换；分析内可切换统计与对标
- [ ] 预测 Tab 同屏展示 EWI、DH 与市电预测曲线，无「指标 / 预测」内层 Tab
- [ ] admin 侧栏顺序：能源分析 → 全部工单 → 智能问答 → 孪生与现场 → 系统管理 → 维修人员 → 用户账号 → 个人中心
- [ ] `/dashboard`、`/energy`、`/stats`、`/benchmark`、`/operations` 访问仍自动跳转至对应 Tab

---

## 4. 按日期汇总表

| 日期 | 负责人 | 条目数 | 阶段主题 |
|------|--------|:------:|----------|
| 2026-06-28 | 李国豪 | 4 | 项目骨架、健康检查、CSV 存储 |
| 2026-06-29 | 李国豪 / 李金东 / 林佳星 | 11+ | 鉴权、Admin、语料、登录前端；**lgh**：工单后端、平台运维、能耗同步 |
| 2026-06-30 | 李金东 / 林佳星 / 李国豪 | 10 | 统计 API、仪表盘、对标、图表 |
| 2026-07-01 | 李金东 / 刘嘉飞 / 林佳星 | 11 | 异常检测、RAG 检索、大屏 |
| 2026-07-02 | 李国豪 / 刘嘉飞 / 林佳星 | 12 | 工单、问答语音、Twin 上传 |
| 2026-07-03 | 四人 | 19 | 孪生 3D、小程序、预测报告、缓存 |
| 2026-07-04 | 四人 + 全体 | 10 | MCP、Docker、文档、集成 |
| 2026-07-05 | 李国豪 / 林佳星 / 刘嘉飞 | 12 | V1.1：课设报单、地址定位、视觉草稿、档案审批 |
| 2026-07-06 | 林佳星 | 4 | V1.2：能源分析合并导航、预测一体页、admin 菜单排序 |

---

## 5. Git 操作示例

### 5.1 首次提交（李国豪 · 06-28）

```bash
cd building_energy_system
git add .gitignore README.md START.txt backend/requirements.txt backend/app/
git commit -m "feat(backend): 项目骨架、健康检查与能耗 CSV 存储"
```

### 5.2 指定作者提交（06-29 李金东）

```bash
git add backend/app/routers/sikong.py backend/app/services/sikong_qa.py backend/app/services/ops_context.py
git -c user.name="李金东" -c user.email="lijindong@example.com" \
  commit -m "feat(rag): 司空 JSONL 语料检索基础"
```

### 5.3 李国豪个人分支 `lgh`（06-29 增量）

```bash
cd building_energy_system
git checkout main
git pull origin main
git checkout -b lgh

# 阶段 2D 文件（见上文 2D 清单 + main.py 依赖的 router/service）
git add START.txt docker-compose.yml docs/GIT_SUBMIT_PLAN.md backend/
git commit -m "feat(backend): 工单后端、平台运维状态与能耗同步"

git checkout main
git merge lgh --no-ff -m "merge: 李国豪 lgh 分支 — 06-29 工单与平台运维"
git push origin lgh
git push origin main
```

### 5.4 合并其他成员分支（李国豪执行）

```bash
git checkout main
git merge feat/ljd-0630 --no-ff -m "merge: 李金东 06-30 统计与导出模块"
git push origin main
```

---

## 6. 未完成功能的处理

功能清单中标注 **「二期」** 或 POC 未完成项，提交时按以下原则：

| 功能 | 清单负责人 | 建议 |
|------|------------|------|
| 完整 RBAC、账号 CRUD | 李国豪 | 仅提交 JWT 三角色 + `auth_gate` + 菜单隔离 |
| 登录日志、操作日志查询 | 李国豪 | 不单独提交；commit message 注明 POC |
| 个人中心（改密等） | 林佳星 | 已实现改密；运维档案申请 + 资质附件（07-05） |
| 课设报单完整流程 | 李国豪 | 06-29 **lgh** 已提交 work_orders 骨架；07-05 阶段 8 补齐前端联动与验收 |
| 高德定位 Key | 李国豪 | 仅存 backend/.env 的 AMAP_WEB_KEY，前端走 /api/location/reverse |
| 能源五页独立菜单 | 林佳星 | V1.2 合并为「能源分析」四 Tab；旧 URL redirect（07-06） |
| 滑动窗口异常（增强） | 刘嘉飞 | 07-04 测试文档说明为迭代项 |
| 企业信息化独立角色 | — | Web 端按菜单隔离，不设独立登录 |

---

## 7. 提交前检查清单

- [ ] 四人 `git config user.name` / `user.email` 已设置
- [ ] 未提交 `backend/.env`、权重 `*.pt`、数据 `*.csv`
- [ ] 未提交 `frontend/node_modules/`、`frontend/dist/`
- [ ] 每阶段后后端可启动：`python -m uvicorn app.main:app --port 8765`
- [ ] 每阶段后前端可构建：`cd frontend && npm run build`
- [ ] commit message 与功能清单「二级模块 + 功能点」可对应
- [ ] 07-04 由李国豪完成最后一次 merge，README 更新四人分工

---

## 8. 相关文档

| 文档 | 路径 |
|------|------|
| 功能清单（Excel） | `docs/智维衡碳-建筑能源智能管理系统-功能清单.xlsx` |
| 需求文档 V1.0 | `docs/需求文档V1.0.md` |
| 项目启动与人员分工 | `docs/PROJECT_KICKOFF_BEFORE_START.md` |
| 启动说明 | `START.txt` |
| 源码说明 | `docs/SOURCE_CODE_DOCUMENT.md` |
| 前端 API 对照 | `docs/API_FRONTEND.md` |

---

*文档版本：v1.3 · 远程 main 已含 06-28/06-29 两提交；**lgh** 分支规范与 2D 增量清单已对齐 [GarfieldFine/energy](https://github.com/GarfieldFine/energy)*
