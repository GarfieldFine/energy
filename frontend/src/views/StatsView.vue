<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import * as api from '@/api'
import { apiUrl } from '@/api/client'
import { InfoFilled, Warning } from '@element-plus/icons-vue'
import EmsDrawer from '@/components/EmsDrawer.vue'
import EmsHelpBtn from '@/components/EmsHelpBtn.vue'
import { ElMessage } from 'element-plus'
import { buildPeriodTableRows, formatIsoRange } from '@/utils/statsDisplay'

/** 异常占比弹窗阈值：>0.15% */
const ANOMALY_WARN_RATIO = 0.0015
const ANOMALY_SERIOUS_RATIO = 0.0015

const buildings = ref([])
const buildingId = ref('')
const dateRange = ref(null)
const loading = ref(false)
/** 避免首屏 loadBuildings 设置 buildingId 时触发重复请求 */
const toolbarReady = ref(false)

const periodData = ref(null)
const anomalies = ref(null)
const cop = ref(null)

const activeTab = ref('period')
const anomalyDialogVisible = ref(false)
const zScoreFormulaDialogVisible = ref(false)

const DEFAULT_Z_THRESHOLD = 3

const displayZThreshold = computed(
  () => anomalies.value?.z_threshold ?? DEFAULT_Z_THRESHOLD,
)

const displayZStats = computed(() => {
  const a = anomalies.value
  if (!a || a.total_hours <= 0) return null
  const mu = a.mean_electricity_kwh
  const sigma = a.std_electricity_kwh
  if (mu == null || sigma == null || Number.isNaN(Number(mu)) || Number.isNaN(Number(sigma))) {
    return null
  }
  return {
    mean: Number(mu),
    std: Number(sigma),
  }
})

const anomalyRatioNum = computed(() => {
  const r = anomalies.value?.ratio
  if (r == null || Number.isNaN(Number(r))) return null
  return Number(r)
})

const anomalySerious = computed(() => {
  const r = anomalyRatioNum.value
  return r != null && r > ANOMALY_SERIOUS_RATIO
})

const anomalyWarn = computed(() => {
  const r = anomalyRatioNum.value
  return r != null && r > ANOMALY_WARN_RATIO && r <= ANOMALY_SERIOUS_RATIO
})

const anomalyDialogLevel = computed(() => {
  if (anomalySerious.value) return 'serious'
  if (anomalyWarn.value) return 'warn'
  return null
})

const kpis = computed(() => {
  const sums = periodData.value?.sums ?? {}
  const elec = Number(sums.electricity_kwh)
  const ar = anomalies.value?.ratio
  const arN = ar != null ? Number(ar) : null
  const pct = arN != null ? (arN * 100).toFixed(2) : '—'
  const copv = cop.value?.mean_chilled_over_elec
  const serious = arN != null && arN > ANOMALY_SERIOUS_RATIO
  const warn = arN != null && arN > ANOMALY_WARN_RATIO && !serious
  return [
    {
      label: '市电累计',
      value: Number.isFinite(elec) ? elec.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) : '—',
      unit: 'kWh',
      trend: '筛选期',
      trendDir: 'neutral',
      trendText: '合计',
      kpiClass: '',
    },
    {
      label: '异常用电占比',
      value: pct,
      unit: '%',
      trend: 'z-score',
      trendDir: arN != null && arN > ANOMALY_WARN_RATIO ? 'up' : 'down',
      trendText: '演示检测',
      kpiClass: serious ? 'myems-kpi-card--accent-danger' : warn ? 'myems-kpi-card--accent-warn' : '',
    },
    {
      label: '冷/电比值',
      value: copv != null ? String(copv) : '—',
      unit: '',
      trend: 'COP 相关',
      trendDir: 'neutral',
      trendText: '小时级',
      kpiClass: '',
    },
    {
      label: '时段行数',
      value: String(periodData.value?.rows ?? '—'),
      unit: '行',
      trend: '数据',
      trendDir: 'neutral',
      trendText: '小时粒度',
      kpiClass: '',
    },
  ]
})

const periodTableRows = computed(() =>
  buildPeriodTableRows(periodData.value?.sums, periodData.value?.means),
)

const periodTimeRangeText = computed(() =>
  formatIsoRange(periodData.value?.time_range?.min, periodData.value?.time_range?.max),
)

const anomalyRatioPct = computed(() => {
  const r = anomalies.value?.ratio
  if (r == null || Number.isNaN(Number(r))) return '—'
  return `${(Number(r) * 100).toFixed(2)}%`
})

const copDisplay = computed(() => {
  const c = cop.value
  if (!c) return null
  const fmt = (x) =>
    x != null && Number.isFinite(Number(x)) ? Number(x).toLocaleString('zh-CN', { maximumFractionDigits: 4 }) : '—'
  return {
    valid_hours: c.valid_hours,
    mean: fmt(c.mean_chilled_over_elec),
    median: fmt(c.median_chilled_over_elec),
  }
})

function formatAnomalyElecCell(v) {
  if (v === '' || v == null) return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

function rangeToParams() {
  if (!dateRange.value || !Array.isArray(dateRange.value) || dateRange.value.length !== 2) {
    return { time_from: undefined, time_to: undefined }
  }
  const [a, b] = dateRange.value
  if (!a || !b) return { time_from: undefined, time_to: undefined }
  return { time_from: a, time_to: b }
}

function filterParams() {
  const { time_from, time_to } = rangeToParams()
  const params = {}
  if (buildingId.value) params.building_id = buildingId.value
  if (time_from) params.time_from = time_from
  if (time_to) params.time_to = time_to
  return params
}

async function loadBuildings() {
  const data = await api.getBuildings()
  buildings.value = data.items ?? []
  if (!buildingId.value && buildings.value.length) {
    buildingId.value = buildings.value[0].building_id ?? buildings.value[0].id ?? ''
  }
}

function anomalyTipStorageKey() {
  const p = filterParams()
  const r = anomalyRatioNum.value
  const ratioKey = r != null ? String(Math.round(r * 10000)) : 'na'
  return `stats_anomaly_tip|${buildingId.value || '_all'}|${p.time_from || ''}|${p.time_to || ''}|${ratioKey}`
}

function maybeShowAnomalyDialog() {
  const total = anomalies.value?.total_hours ?? 0
  const level = anomalyDialogLevel.value
  if (total <= 0 || !level) {
    anomalyDialogVisible.value = false
    return
  }
  if (sessionStorage.getItem(anomalyTipStorageKey())) return
  anomalyDialogVisible.value = true
}

function dismissAnomalyDialog(goToTab = false) {
  anomalyDialogVisible.value = false
  sessionStorage.setItem(anomalyTipStorageKey(), '1')
  if (goToTab) activeTab.value = 'anomalies'
}

function goAnomalyDetail() {
  dismissAnomalyDialog(true)
}

async function loadAllPanels() {
  const p = filterParams()
  loading.value = true
  try {
    const [per, ano, cp] = await Promise.all([
      api.getStatsPeriod(p).catch(() => null),
      api.getStatsAnomalies({ ...p, z_threshold: 3 }).catch(() => null),
      api.getStatsCopProxy(p).catch(() => null),
    ])
    periodData.value = per
    anomalies.value = ano
    cop.value = cp
    maybeShowAnomalyDialog()
  } catch (e) {
    ElMessage.error(e.message ?? '加载失败')
  } finally {
    loading.value = false
  }
}

function exportCsv() {
  const p = filterParams()
  const q = new URLSearchParams()
  if (p.building_id) q.set('building_id', p.building_id)
  if (p.time_from) q.set('time_from', p.time_from)
  if (p.time_to) q.set('time_to', p.time_to)
  const url = apiUrl(`/api/stats/export/csv${q.toString() ? `?${q.toString()}` : ''}`)
  window.open(url, '_blank')
}

onMounted(async () => {
  await loadBuildings()
  await loadAllPanels()
  toolbarReady.value = true
})

watch(
  [buildingId, dateRange],
  async () => {
    if (!toolbarReady.value) return
    await loadAllPanels()
  },
  { deep: true },
)
</script>

<template>
  <div class="myems-page stats-view">
    <EmsDrawer
      v-model="anomalyDialogVisible"
      title="用电异常提示"
      size="440px"
      @close="dismissAnomalyDialog(false)"
    >
      <div class="stats-anomaly-body">
        <div
          class="stats-anomaly-icon"
          :class="{
            'stats-anomaly-icon--serious': anomalyDialogLevel === 'serious',
            'stats-anomaly-icon--warn': anomalyDialogLevel === 'warn',
          }"
        >
          <el-icon :size="22"><Warning /></el-icon>
        </div>
        <p class="stats-anomaly-lead">
          当前筛选条件下，异常用电占比为
          <strong class="num-font">{{ anomalyRatioPct }}</strong>
          （共 <strong class="num-font">{{ anomalies?.anomaly_hours ?? 0 }}</strong> /
          {{ anomalies?.total_hours ?? 0 }} 小时）。
        </p>
      </div>
      <template #footer>
        <el-button round @click="dismissAnomalyDialog(false)">知道了</el-button>
        <el-button type="primary" round @click="goAnomalyDetail">查看异常明细</el-button>
      </template>
    </EmsDrawer>

    <div class="page-head page-head--end">
      <el-button round :icon="InfoFilled" @click="zScoreFormulaDialogVisible = true">
        Z-score 异常检测说明
      </el-button>
    </div>

    <EmsDrawer v-model="zScoreFormulaDialogVisible" title="用电异常 · Z-score 检测说明" size="560px">
      <code class="formula-expr">
        z = (x − μ) / σ &nbsp;&nbsp;|z| &gt; {{ displayZThreshold }} → 记为异常小时
      </code>
      <ul class="formula-detail">
        <li>
          <strong>x</strong>：筛选条件下每小时 <code>electricity_kwh</code>（市电 kWh）
        </li>
        <li>
          <strong>μ</strong>：该时段全部有效小时电耗的算术平均；
          <strong>σ</strong>：总体标准差（<code>ddof=0</code>）
        </li>
        <li>
          <strong>异常占比</strong> = 异常小时数 ÷ 统计小时数；明细表最多展示 50 条样本
        </li>
        <li>σ = 0 或无法计算时不出异常结果，并提示「标准差为 0」</li>
        <li>演示级全局 z-score；与能效对标「综合分」独立，仅用于异常预警与运维关注</li>
      </ul>
      <div v-if="displayZStats" class="weight-tags">
        <el-tag type="info" effect="plain" size="small">
          当前 μ = {{ displayZStats.mean.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) }} kWh/h
        </el-tag>
        <el-tag type="info" effect="plain" size="small">
          当前 σ = {{ displayZStats.std.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) }} kWh/h
        </el-tag>
        <el-tag type="warning" effect="plain" size="small">
          阈值 |z| &gt; {{ displayZThreshold }}
        </el-tag>
        <el-tag v-if="anomalies?.anomaly_hours != null" type="info" effect="plain" size="small">
          已检出 {{ anomalies.anomaly_hours }} / {{ anomalies.total_hours }} 小时
        </el-tag>
      </div>
      <p v-else class="formula-footnote">变更顶部空间或统计期并加载后，可显示当前筛选条件下的 μ、σ。</p>
      <template #footer>
        <el-button type="primary" round @click="zScoreFormulaDialogVisible = false">知道了</el-button>
      </template>
    </EmsDrawer>

    <div class="myems-toolbar myems-toolbar--dense">
      <el-form label-width="0">
        <el-row :gutter="[10, 8]">
          <el-col :xs="24" :sm="12" :md="6">
            <el-form-item>
              <el-select
                v-model="buildingId"
                clearable
                placeholder="空间 · 全部建筑"
                class="w-full"
                filterable
                size="small"
              >
                <el-option
                  v-for="b in buildings"
                  :key="JSON.stringify(b)"
                  :label="b.building_id ?? b.name ?? String(b)"
                  :value="b.building_id ?? b.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="24" :md="18">
            <el-form-item>
              <el-date-picker
                v-model="dateRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="统计期 · 开始"
                end-placeholder="统计期 · 结束"
                format="YYYY-MM-DD HH:mm"
                value-format="YYYY-MM-DD HH:mm:ss"
                class="w-full"
                size="small"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <div class="toolbar-actions">
          <el-button @click="exportCsv">导出 CSV</el-button>
        </div>
      </el-form>
    </div>

    <el-row :gutter="12" class="myems-kpi-row">
      <el-col v-for="(k, i) in kpis" :key="i" :xs="24" :sm="12" :md="6">
        <div class="myems-kpi-card" :class="k.kpiClass">
          <div class="myems-kpi-label">{{ k.label }}</div>
          <div>
            <span class="myems-kpi-value num-font">{{ k.value }}</span>
            <span class="myems-kpi-unit">{{ k.unit }}</span>
          </div>
          <div
            class="myems-kpi-trend"
            :class="{
              'myems-kpi-trend--up': k.trendDir === 'up',
              'myems-kpi-trend--down': k.trendDir === 'down',
            }"
          >
            {{ k.trend }} · {{ k.trendText }}
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>指标与明细</span>
      </div>
      <el-tabs v-model="activeTab" type="card" class="analysis-tabs">
        <el-tab-pane label="时段汇总" name="period">
          <div v-loading="loading" class="detail-tab">
            <template v-if="periodData && periodData.rows > 0">
              <div class="detail-tab-toolbar">
                <EmsHelpBtn title="汇总表说明" size="400px">
                  <p>「合计」为筛选期内各指标累加；「均值」为按小时平均。</p>
                  <p>气温、湿度类指标合计无业务含义时显示为 —，请以均值为准。</p>
                </EmsHelpBtn>
              </div>
              <el-descriptions :column="3" border size="small" class="detail-desc mb">
                <el-descriptions-item label="时间范围" :span="2">
                  <span class="detail-mono">{{ periodTimeRangeText }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="数据行数">
                  <el-tag size="small" type="info" effect="plain">{{ periodData.rows }} 行</el-tag>
                </el-descriptions-item>
                <el-descriptions-item v-if="periodData.buildings?.length" label="涉及建筑" :span="3">
                  <span class="detail-buildings">{{ periodData.buildings.join('、') }}</span>
                </el-descriptions-item>
              </el-descriptions>
              <el-table
                v-if="periodTableRows.length"
                :data="periodTableRows"
                size="small"
                class="detail-table data-table--borderless"
                max-height="440"
                empty-text="无汇总字段"
              >
                <el-table-column prop="label" label="指标" min-width="120" fixed="left" />
                <el-table-column prop="unit" label="单位" width="72" align="center" />
                <el-table-column prop="sumFmt" label="合计" min-width="120" align="right" />
                <el-table-column prop="meanFmt" label="均值" min-width="120" align="right" />
              </el-table>
            </template>
            <el-empty v-else description="变更顶部空间或统计期后将自动加载" :image-size="80" />
          </div>
        </el-tab-pane>
        <el-tab-pane label="用电异常" name="anomalies">
          <div v-loading="loading" class="detail-tab">
            <div class="anomaly-tab-head">
              <EmsHelpBtn title="用电异常检测说明">
                <p>基于筛选时段市电 hourly 数据，使用 Z-score 识别异常小时。</p>
                <p>点击下方「Z-score 说明」可查看公式与阈值。</p>
              </EmsHelpBtn>
              <el-button round :icon="InfoFilled" @click="zScoreFormulaDialogVisible = true">
                Z-score 说明
              </el-button>
            </div>
            <el-alert
              v-if="anomalies?.note"
              :title="anomalies.note"
              type="warning"
              show-icon
              :closable="false"
              class="mb"
            />
            <template v-if="anomalies && anomalies.total_hours > 0">
              <el-descriptions :column="2" border size="small" class="detail-desc mb">
                <el-descriptions-item label="统计小时数">{{ anomalies.total_hours }}</el-descriptions-item>
                <el-descriptions-item label="异常小时数">
                  <el-tag :type="anomalies.anomaly_hours > 0 ? 'warning' : 'success'" size="small" effect="light">
                    {{ anomalies.anomaly_hours }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="异常占比">
                  <span class="detail-em">{{ anomalyRatioPct }}</span>
                  <span class="detail-sub">（相对全部小时）</span>
                </el-descriptions-item>
                <el-descriptions-item label="z 阈值">{{ anomalies.z_threshold }}</el-descriptions-item>
              </el-descriptions>
              <div v-if="anomalies.samples?.length" class="detail-table-wrap">
                <div class="detail-table-title">异常样本（最多 50 条）</div>
                <el-table
                  :data="anomalies.samples"
                  size="small"
                  class="detail-table data-table--borderless"
                  max-height="400"
                >
                  <el-table-column prop="building_id" label="建筑" min-width="200" show-overflow-tooltip />
                  <el-table-column prop="monitor_time" label="监测时间" min-width="168" />
                  <el-table-column label="市电 (kWh)" min-width="110" align="right">
                    <template #default="{ row }">
                      {{ formatAnomalyElecCell(row.electricity_kwh) }}
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <el-empty v-else description="当前阈值下未检出异常小时" :image-size="72" />
            </template>
            <el-empty v-else-if="!loading" description="无异常分析数据" :image-size="80" />
          </div>
        </el-tab-pane>
        <el-tab-pane label="COP 演示" name="cop">
          <div v-loading="loading" class="detail-tab">
            <template v-if="cop && cop.valid_hours > 0 && copDisplay">
              <el-descriptions :column="1" border size="small" class="detail-desc">
                <el-descriptions-item label="有效小时数">{{ copDisplay.valid_hours }}</el-descriptions-item>
                <el-descriptions-item label="冷量/市电 · 均值">
                  <span class="detail-mono">{{ copDisplay.mean }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="冷量/市电 · 中位数">
                  <span class="detail-mono">{{ copDisplay.median }}</span>
                </el-descriptions-item>
              </el-descriptions>
            </template>
            <el-empty v-else-if="!loading" description="暂无 COP 分析结果" :image-size="80" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}

.page-head--end {
  justify-content: flex-end;
}

.formula-expr {
  display: block;
  padding: 12px 14px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  font-size: 13px;
  color: #1f2329;
  line-height: 1.6;
  word-break: break-all;
}

.formula-detail {
  margin: 12px 0 0;
  padding-left: 20px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.55);
  line-height: 1.75;
}

.formula-detail code {
  font-size: 11px;
  background: #f0f0f0;
  padding: 1px 4px;
  border-radius: 3px;
}

.weight-tags {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.formula-footnote {
  margin: 12px 0 0;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  line-height: 1.5;
}

.anomaly-tab-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.anomaly-tab-hint {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.stats-anomaly-body {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.stats-anomaly-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #fff7e6;
  color: #d48806;
}

.stats-anomaly-icon--serious {
  background: #fff1f0;
  color: #cf1322;
}

.stats-anomaly-lead {
  margin: 0 0 8px;
  font-size: 14px;
  line-height: 1.65;
  color: #4e5969;
}

.stats-anomaly-lead strong {
  color: #1f2329;
}

.w-full {
  width: 100%;
}

.label-cal {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.toolbar-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}

.section-hint {
  font-size: 12px;
  font-weight: 400;
  color: rgba(0, 0, 0, 0.35);
}

.mb {
  margin-bottom: 12px;
}

.analysis-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.detail-tab {
  min-height: 120px;
}

.detail-desc :deep(.el-descriptions__label) {
  width: 108px;
  font-weight: 500;
}

.detail-mono {
  font-variant-numeric: tabular-nums;
  word-break: break-all;
}

.detail-buildings {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.5;
}

.detail-table :deep(.el-table__header th) {
  background: #fafafa;
}

.col-hint {
  display: block;
  font-size: 11px;
  font-weight: 400;
  color: rgba(0, 0, 0, 0.38);
  line-height: 1.2;
  margin-top: 2px;
}

.detail-footnote {
  margin: 10px 0 0;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.42);
  line-height: 1.5;
}

.detail-em {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.detail-sub {
  margin-left: 6px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.42);
}

.detail-table-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.75);
  margin-bottom: 8px;
}

.detail-table-wrap {
  margin-top: 4px;
}

</style>
