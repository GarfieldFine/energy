import { http } from './client'

export function postAuthLogin(body) {
  return http.post('/api/auth/login', body).then((r) => r.data)
}

export function getAuthMe() {
  return http.get('/api/auth/me').then((r) => r.data)
}

export function getAuthDemoAccounts() {
  return http.get('/api/auth/demo-accounts').then((r) => r.data)
}

export function getHealth() {
  return http.get('/health').then((r) => r.data)
}

export function getBuildings() {
  return http.get('/api/energy/buildings').then((r) => r.data)
}

export function getEnergyRecords(params) {
  return http.get('/api/energy/records', { params }).then((r) => r.data)
}

export function getStatsPeriod(params) {
  return http.get('/api/stats/period', { params }).then((r) => r.data)
}

export function getStatsAnomalies(params) {
  return http.get('/api/stats/anomalies', { params }).then((r) => r.data)
}

export function getStatsCopProxy(params) {
  return http.get('/api/stats/cop-proxy', { params }).then((r) => r.data)
}

export function getStatsTimeseries(params) {
  return http.get('/api/stats/timeseries', { params }).then((r) => r.data)
}

export function getMetricsCatalog() {
  return http.get('/api/stats/metrics-catalog').then((r) => r.data)
}

export function getBenchmarkScoreboard(params) {
  return http.get('/api/stats/benchmark/scoreboard', { params }).then((r) => r.data)
}

export function getKbSearch(params) {
  return http.get('/api/kb/search', { params }).then((r) => r.data)
}

export function getKbStatus() {
  return http.get('/api/kb/status').then((r) => r.data)
}

export function postKbRagDemo(body) {
  return http.post('/api/kb/rag-demo', body).then((r) => r.data)
}

export function getSikongSearch(params) {
  return http.get('/api/sikong/search', { params }).then((r) => r.data)
}

export function getSikongStatus() {
  return http.get('/api/sikong/status').then((r) => r.data)
}

export function postSikongRagDemo(body) {
  return http.post('/api/sikong/rag-demo', body).then((r) => r.data)
}

/** @param {{ query: string, kb_limit?: number, sikong_limit?: number, use_llm?: boolean|null, building_id?: string|null }} body */
export function postAssistantRagAnswer(body) {
  return http.post('/api/assistant/rag-answer', body).then((r) => r.data)
}

export function getAssistantLlmStatus() {
  return http.get('/api/assistant/llm-status').then((r) => r.data)
}

/** 百度语音识别是否已在后端配置 */
export function getAssistantSpeechStatus() {
  return http.get('/api/assistant/speech/status').then((r) => r.data)
}

/**
 * 上传 16kHz WAV 进行语音转文字
 * @param {Blob} wavBlob
 */
export function postAssistantSpeechToText(wavBlob) {
  const fd = new FormData()
  fd.append('file', wavBlob, 'speech.wav')
  return http
    .post('/api/assistant/speech-to-text', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { format: 'wav', rate: 16000 },
      timeout: 60_000,
    })
    .then((r) => r.data)
}

/** 队友 Chatchat 转发：是否配置、能否连通 */
export function getChatchatStatus() {
  return http.get('/api/chatchat/status').then((r) => r.data)
}

/**
 * 知识库对话，转发至 Chatchat POST /chat/kb_chat
 * @param {Record<string, unknown>} body query, kb_name, mode?: 'local_kb', stream?: false, …
 */
/** 解析 Chatchat 响应：保证得到对象后再取 choices[0].message.content */
export function postChatchatKbChat(body) {
  return http.post('/api/chatchat/kb-chat', body).then((r) => {
    let data = r.data
    if (typeof data === 'string') {
      try {
        data = JSON.parse(data)
      } catch {
        /* 保持字符串，由前端 parseChatchatAnswer 处理 */
      }
    }
    return data
  })
}

export function postAssistantKnowledgeMerge(body) {
  return http.post('/api/assistant/knowledge-merge', body).then((r) => r.data)
}

export function getIncidents(params) {
  return http.get('/api/incidents', { params }).then((r) => r.data)
}

export function getIncidentsSummary() {
  return http.get('/api/incidents/summary').then((r) => r.data)
}

export function postIncident(body) {
  return http.post('/api/incidents', body).then((r) => r.data)
}

export function patchIncident(id, body) {
  return http.patch(`/api/incidents/${id}`, body).then((r) => r.data)
}

export function getIncident(id) {
  return http.get(`/api/incidents/${id}`).then((r) => r.data)
}

export function deleteIncident(id) {
  return http.delete(`/api/incidents/${id}`).then((r) => r.data)
}

export function getAdminStatus() {
  return http.get('/api/admin/status').then((r) => r.data)
}

export function postAdminReload() {
  return http.post('/api/admin/reload').then((r) => r.data)
}

export function postAdminKbReindex() {
  return http.post('/api/admin/kb/reindex').then((r) => r.data)
}

export function getAdminDatasetImportStatus() {
  return http.get('/api/admin/dataset/import-status').then((r) => r.data)
}

/** @param {File} file */
export function postAdminDatasetUploadEnergy(file) {
  const fd = new FormData()
  fd.append('file', file)
  return http
    .post('/api/admin/dataset/upload-energy', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((r) => r.data)
}

/** @param {File} file */
export function postAdminDatasetUploadMetadata(file) {
  const fd = new FormData()
  fd.append('file', file)
  return http
    .post('/api/admin/dataset/upload-metadata', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((r) => r.data)
}

/** @param {File} file */
export function postAdminDatasetUploadDictionary(file) {
  const fd = new FormData()
  fd.append('file', file)
  return http
    .post('/api/admin/dataset/upload-dictionary', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((r) => r.data)
}

export function getMcpTools() {
  return http.get('/api/mcp/tools').then((r) => r.data)
}

export function getV2TwinScene() {
  return http.get('/api/v2/twin/scene').then((r) => r.data)
}

/** @param {{ building_id?: string }} [params] */
export function getV2OpsIndicators(params) {
  return http.get('/api/v2/ops/indicators', { params }).then((r) => r.data)
}

/** @param {{ building_id?: string }} [params] */
export function getV2OpsSuggestions(params) {
  return http.get('/api/v2/ops/suggestions', { params }).then((r) => r.data)
}

export function getV2ForecastEnergy(params) {
  return http.get('/api/v2/forecast/energy', { params }).then((r) => r.data)
}

export function getDataDictionary() {
  return http.get('/api/meta/data-dictionary').then((r) => r.data)
}

export function postV2VisionAnalyze(body) {
  return http.post('/api/v2/vision/analyze', body).then((r) => r.data)
}

/** @param {File} file @param {{ mode?: string, prompt?: string, conf?: number, iou?: number, imgsz?: number }} [params] */
export function postV2VisionUpload(file, params = {}) {
  const fd = new FormData()
  fd.append('file', file)
  return http
    .post('/api/v2/vision/upload', fd, {
      // 覆盖默认 application/json，确保 FastAPI 能正确解析 UploadFile
      headers: { 'Content-Type': 'multipart/form-data' },
      params: {
        ...(params.mode != null && params.mode !== '' ? { mode: String(params.mode) } : {}),
        ...(params.prompt != null && params.prompt !== '' ? { prompt: params.prompt } : {}),
        ...(params.conf != null && !Number.isNaN(Number(params.conf))
          ? { conf: Number(params.conf) }
          : {}),
        ...(params.iou != null && !Number.isNaN(Number(params.iou)) ? { iou: Number(params.iou) } : {}),
        ...(params.imgsz != null && !Number.isNaN(Number(params.imgsz))
          ? { imgsz: Number(params.imgsz) }
          : {}),
      },
    })
    .then((r) => r.data)
}
