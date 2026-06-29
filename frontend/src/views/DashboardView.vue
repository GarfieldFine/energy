<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  RefreshRight,
  DataLine,
  Histogram,
  TrendCharts,
  Monitor,
} from '@element-plus/icons-vue'
import AppChart from '@/components/AppChart.vue'
import AnimatedNumber from '@/components/AnimatedNumber.vue'
import EmsDrawer from '@/components/EmsDrawer.vue'
import EmsHelpBtn from '@/components/EmsHelpBtn.vue'
import * as api from '@/api'
import { usePolling } from '@/composables/usePolling'
import { useAuthStore } from '@/stores/auth'
import { openDataScreen } from '@/utils/workspaceNav'
import { ElMessage } from 'element-plus'

const router = useRouter()
const auth = useAuthStore()

const loading = ref(true)
const lastUpdated = ref(null)
const health = ref(null)
const incidentSum = ref(null)
const buildings = ref({ items: [] })
const benchmark = ref(null)
const period = ref(null)
const anomalies = ref(null)
const timeseries = ref(null)
/** 与饼图联动：当前折线指标 */
const selectedMetric = ref('electricity_kwh')

const REFRESH_MS = 30_000
const incidentTipVisible = ref(false)

/** 异常占比提醒阈值：>0.15% */
const ANOMALY_WARN_RATIO = 0.0015
const ANOMALY_SERIOUS_RATIO = 0.0015

const PIE_NAME_TO_METRIC = {
  市电: 'electricity_kwh',
  光伏: 'solar_kwh',
  冷量当量: 'chilledwater_kwh_eq',
  热水: 'hotwater_kwh',
}

const METRIC_TO_PIE_NAME = {
  electricity_kwh: '市电',
  solar_kwh: '光伏',
  chilledwater_kwh_eq: '冷量当量',
  hotwater_kwh: '热水',
}

const METRIC_LABEL_SHORT = {
  electricity_kwh: '市电',
  solar_kwh: '光伏',
  chilledwater_kwh_eq: '冷量当量',
  hotwater_kwh: '热水',
  water_m3: '用水',
}

/** 驾驶舱首屏 KPI */
const cockpitKpis = computed(() => {
  const sums = period.value?.sums ?? {}
  const elec = Number(sums.electricity_kwh)
  const water = Number(sums.water_m3)
  const solar = Number(sums.solar_kwh)
  const ap = anomalyPct.value
  const apNum = ap != null ? Number(ap) : null
  const pend = pendingIncidents.value
  return [
    {
      key: 'elec',
      label: '市电累计',
      unit: 'kWh',
      delta: '环比 —',
      animValue: Number.isFinite(elec) ? elec : null,
      animDigits: 0,
      stripClass: '',
    },
    {
      key: 'water',
      label: '用水累计',
      unit: 'm³',
      delta: '环比 —',
      animValue: Number.isFinite(water) ? water : null,
      animDigits: 1,
      stripClass: '',
    },
    {
      key: 'solar',
      label: '光伏累计',
      unit: 'kWh',
      delta: '环比 —',
      animValue: Number.isFinite(solar) ? solar : null,
      animDigits: 0,
      stripClass: '',
    },
    {
      key: 'anomaly',
      label: '异常用电占比',
      unit: apNum != null ? '%' : '',
      delta: '较监测阈值',
      animValue: apNum,
      animDigits: 2,
      stripClass: anomalySerious.value
        ? 'dash-kpi-card--strip-danger'
        : anomalyWarn.value
          ? 'dash-kpi-card--strip-warn'
          : '',
    },
    {
      key: 'pending',
      label: '待处理工单',
      unit: '条',
      delta: '环比 —',
      animValue: pend,
      animDigits: 0,
      stripClass: pend > 0 ? 'dash-kpi-card--strip-warn' : '',
    },
  ]
})

const metricMeta = {
  electricity_kwh: { label: '市电用电', unit: 'kWh', short: '电' },
  solar_kwh: { label: '光伏发电', unit: 'kWh', short: '光' },
  water_m3: { label: '用水量', unit: 'm³', short: '水' },
  hotwater_kwh: { label: '热水能耗', unit: 'kWh', short: '热' },
  chilledwater_kwh_eq: { label: '冷量当量', unit: 'kWh', short: '冷' },
}

const buildingIdForSeries = computed(() => {
  const items = buildings.value?.items ?? []
  if (!items.length) return ''
  const b = items[0]
  return b.building_id ?? b.id ?? ''
})

const anomalyPct = computed(() => {
  const r = anomalies.value?.ratio
  if (r == null || Number.isNaN(r)) return null
  return (r * 100).toFixed(2)
})

const anomalySerious = computed(() => {
  const r = anomalies.value?.ratio ?? 0
  return r > ANOMALY_SERIOUS_RATIO
})

const anomalyWarn = computed(() => {
  const r = anomalies.value?.ratio ?? 0
  return r > ANOMALY_WARN_RATIO && r <= ANOMALY_SERIOUS_RATIO
})

const pendingIncidents = computed(() => incidentSum.value?.pending ?? 0)

function fmtNum(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(n)
}

const pieOption = computed(() => {
  const sums = period.value?.sums ?? {}
  const parts = [
    { name: '市电', value: Number(sums.electricity_kwh) || 0 },
    { name: '光伏', value: Number(sums.solar_kwh) || 0 },
    { name: '冷量当量', value: Number(sums.chilledwater_kwh_eq) || 0 },
    { name: '热水', value: Number(sums.hotwater_kwh) || 0 },
  ].filter((p) => p.value > 0)
  if (parts.length === 0) return null
  const sel = METRIC_TO_PIE_NAME[selectedMetric.value] ?? '市电'
  const totalEnergy = parts.reduce((a, p) => a + p.value, 0)
  return {
    color: ['#1890ff', '#52c41a', '#69c0ff', '#95de64'],
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { color: '#595959', fontSize: 11 } },
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: '36%',
        style: {
          text: fmtNum(totalEnergy),
          fill: 'var(--ems-text-primary, #1f2329)',
          fontSize: 20,
          fontWeight: 600,
          fontFamily: 'var(--ems-font-number), sans-serif',
        },
      },
      {
        type: 'text',
        left: 'center',
        top: '46%',
        style: {
          text: '分项累计',
          fill: 'var(--ems-text-placeholder, #86909c)',
          fontSize: 12,
        },
      },
    ],
    series: [
      {
        type: 'pie',
        radius: ['50%', '72%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        selectedMode: 'single',
        selectedOffset: 6,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { color: '#595959', fontSize: 11 },
        data: parts.map((p) => ({
          ...p,
          selected: p.name === sel,
        })),
      },
    ],
  }
})

const lineChartHeading = computed(() => {
  const m = selectedMetric.value
  const lab = metricMeta[m]?.label ?? METRIC_LABEL_SHORT[m] ?? '市电用电'
  return `${lab}趋势`
})

const lineOption = computed(() => {
  const labels = timeseries.value?.labels ?? []
  const values = timeseries.value?.values ?? []
  const unit = timeseries.value?.unit_hint ?? 'kWh'
  if (!labels.length) return null
  const nums = values
    .map((v) => (v == null || Number.isNaN(Number(v)) ? null : Number(v)))
    .filter((v) => v != null)
  const mean = nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null
  return {
    color: ['#1890ff'],
    tooltip: { trigger: 'axis' },
    toolbox: {
      show: true,
      right: 8,
      top: 0,
      feature: {
        magicType: {
          type: ['line', 'bar'],
          title: { line: '折线', bar: '柱状' },
        },
      },
    },
    grid: { left: 48, right: 20, top: 52, bottom: 28 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#d9d9d9' } },
      axisLabel: { color: '#8c8c8c', fontSize: 10, rotate: labels.length > 40 ? 35 : 0 },
    },
    yAxis: {
      type: 'value',
      name: unit,
      nameTextStyle: { color: '#8c8c8c', fontSize: 11 },
      axisLine: { show: false },
      axisLabel: { color: '#8c8c8c' },
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
    },
    series: [
      {
        type: 'line',
        data: values,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#1890ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(24, 144, 255, 0.28)' },
              { offset: 1, color: 'rgba(24, 144, 255, 0)' },
            ],
          },
        },
        markLine:
          mean != null
            ? {
                silent: true,
                symbol: 'none',
                label: { show: true, formatter: '时段均值', color: '#8c8c8c', fontSize: 11 },
                lineStyle: { type: 'dashed', color: '#faad14', width: 1 },
                data: [{ yAxis: mean }],
              }
            : undefined,
      },
    ],
  }
})

const barBenchmarkOption = computed(() => {
  const labels = benchmark.value?.chart?.labels ?? []
  const scores = benchmark.value?.chart?.scores ?? []
  if (!labels.length) return null
  return {
    color: ['#1890ff'],
    tooltip: { trigger: 'axis' },
    grid: { left: 44, right: 16, top: 24, bottom: labels.length > 6 ? 48 : 32 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { rotate: 28, fontSize: 10, color: '#8c8c8c' },
      axisLine: { lineStyle: { color: '#d9d9d9' } },
    },
    yAxis: {
      type: 'value',
      max: 100,
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
      axisLabel: { color: '#8c8c8c' },
    },
    series: [{ type: 'bar', data: scores, barMaxWidth: 28, itemStyle: { borderRadius: [4, 4, 0, 0] } }],
  }
})

async function loadTimeseriesForBuilding() {
  const bid = buildingIdForSeries.value
  if (!bid) return
  timeseries.value = await api
    .getStatsTimeseries({
      building_id: bid,
      metric: selectedMetric.value,
      limit: 400,
    })
    .catch(() => null)
}

function onPieChartClick(params) {
  const m = PIE_NAME_TO_METRIC[params?.name]
  if (!m) return
  selectedMetric.value = m
  loadTimeseriesForBuilding()
}

async function loadData(showToastError = true, silent = false) {
  if (!silent) loading.value = true
  try {
    const [h, inc, b, bench, per, ano] = await Promise.all([
      api.getHealth().catch(() => null),
      api.getIncidentsSummary().catch(() => null),
      api.getBuildings().catch(() => ({ items: [] })),
      api.getBenchmarkScoreboard({ top_n: 8 }).catch(() => null),
      api.getStatsPeriod({}).catch(() => null),
      api.getStatsAnomalies({ z_threshold: 3 }).catch(() => null),
    ])
    health.value = h
    incidentSum.value = inc
    buildings.value = b
    benchmark.value = bench
    period.value = per
    anomalies.value = ano

    await loadTimeseriesForBuilding()

    lastUpdated.value = new Date()

    const pending = inc?.pending ?? 0
    if (pending > 0 && !sessionStorage.getItem('dash_incident_tip_dismissed')) {
      incidentTipVisible.value = true
    }
  } catch (e) {
    if (showToastError) ElMessage.error(e.message ?? '加载失败，请确认后端已启动')
  } finally {
    if (!silent) loading.value = false
  }
}

function goIncidents() {
  router.push('/incidents')
}

function dismissIncidentTip(goToList = false) {
  incidentTipVisible.value = false
  sessionStorage.setItem('dash_incident_tip_dismissed', '1')
  if (goToList) goIncidents()
}

function goPath(p) {
  router.push(p)
}

function goStats() {
  router.push('/stats')
}

function goBenchmark() {
  router.push('/benchmark')
}

function onOpenDataScreen() {
  openDataScreen(router)
}

onMounted(() => loadData())
usePolling(() => loadData(false, true), REFRESH_MS)
</script>

<template>
  <div class="dash-container">
    <div v-if="loading" class="dash-skeleton-wrap" aria-busy="true">
      <el-skeleton animated>
        <template #template>
          <el-skeleton-item variant="h3" style="width: 220px; margin-bottom: 16px" />
          <el-skeleton-item variant="text" style="width: 100px; margin: 0 0 12px" />
          <div class="sk-kpis">
            <el-skeleton-item v-for="j in 5" :key="j" variant="rect" class="sk-kpi-cell" />
          </div>
          <div class="sk-charts">
            <el-skeleton-item variant="rect" class="sk-chart-main" />
            <el-skeleton-item variant="rect" class="sk-chart-side" />
          </div>
        </template>
      </el-skeleton>
    </div>

    <template v-else>
    <div v-if="auth.hasRoute('stats') && (anomalySerious || anomalyWarn)" class="alert-stack">
      <el-alert
        v-if="anomalySerious || anomalyWarn"
        :title="`用电异常监测：异常时段占比 ${anomalyPct ?? '—'}%`"
        :type="anomalySerious ? 'error' : 'warning'"
        show-icon
        :closable="false"
        class="alert-item"
        @click="goStats"
      >
        <template #default>
          <span class="alert-link">建议查看「统计分析」中的异常明细。</span>
        </template>
      </el-alert>
    </div>

    <EmsDrawer v-model="incidentTipVisible" title="待办提醒" size="400px" @close="dismissIncidentTip(false)">
      <p class="incident-tip-body">
        当前有 <strong class="num-font">{{ pendingIncidents }}</strong> 条待处理运维工单，可前往工单页面查看与处理。
      </p>
      <template #footer>
        <el-button round @click="dismissIncidentTip(false)">稍后</el-button>
        <el-button type="primary" round @click="dismissIncidentTip(true)">查看工单</el-button>
      </template>
    </EmsDrawer>

    <header class="dash-header-mini dash-header-single">
      <h1 class="ems-page-title">能源管理看板</h1>
      <div class="dash-action-group">
        <el-button v-if="auth.hasRoute('screen')" round :icon="Monitor" @click="onOpenDataScreen">
          数据大屏
        </el-button>
        <el-tooltip
          :content="lastUpdated ? `上次更新 ${lastUpdated.toLocaleTimeString('zh-CN')} · 每 ${REFRESH_MS / 1000}s 自动刷新` : '刷新数据'"
          placement="bottom"
        >
          <el-button type="primary" round :icon="RefreshRight" aria-label="刷新" @click="loadData()">
            刷新
          </el-button>
        </el-tooltip>
      </div>
    </header>

    <div class="dash-kpi-mosaic" aria-label="核心监测">
      <div
        v-for="k in cockpitKpis"
        :key="k.key"
        class="dash-kpi-card dash-kpi-card--cockpit"
        :class="k.stripClass"
      >
        <div class="dash-kpi-label">{{ k.label }}</div>
        <div class="dash-kpi-value-row">
          <span
            v-if="typeof k.animValue === 'number' && !Number.isNaN(k.animValue)"
            class="dash-kpi-num kpi-val num-font"
          >
            <AnimatedNumber
              :key="`${k.key}-${lastUpdated?.getTime() ?? 0}`"
              :value="k.animValue"
              :digits="k.animDigits ?? 0"
            />
          </span>
          <span v-else class="dash-kpi-num kpi-val num-font">—</span>
          <span v-if="k.unit" class="dash-kpi-unit">{{ k.unit }}</span>
        </div>
        <div class="dash-kpi-delta">{{ k.delta }}</div>
      </div>
    </div>

    <el-row :gutter="[12, 12]" class="dash-chart-row">
      <el-col :xs="24" :lg="16">
        <div class="chart-surface">
          <div class="chart-surface-title">
            <span>{{ lineChartHeading }}</span>
            <EmsHelpBtn title="趋势图说明">
              <p>当前建筑：{{ buildingIdForSeries || '无' }}。</p>
              <p>饼图扇区可切换折线指标；折线展示筛选期内的时序趋势。</p>
            </EmsHelpBtn>
          </div>
          <AppChart v-if="lineOption" class="chart-h" :option="lineOption" />
          <el-empty v-else description="暂无趋势数据" :image-size="72">
            <template #image>
              <el-icon class="empty-ico" :size="52"><DataLine /></el-icon>
            </template>
            <el-button type="primary" @click="loadData()">重新加载</el-button>
          </el-empty>
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="chart-surface">
          <div class="chart-surface-title">
            <span>能源构成（累计）</span>
            <EmsHelpBtn title="能源构成说明">
              <p>展示筛选期内各分项能源累计占比。</p>
              <p>点击扇区可联动左侧趋势图指标。</p>
            </EmsHelpBtn>
          </div>
          <AppChart
            v-if="pieOption"
            class="chart-h chart-h--pie"
            :option="pieOption"
            enable-click
            @chart-click="onPieChartClick"
          />
          <el-empty v-else description="无可拆分能源数据" :image-size="72">
            <template #image>
              <el-icon class="empty-ico" :size="52"><Histogram /></el-icon>
            </template>
            <el-button type="primary" link @click="goPath('/energy')">前往能源明细</el-button>
          </el-empty>
        </div>
      </el-col>
    </el-row>

    <div class="chart-surface dash-benchmark-card">
      <div class="chart-surface-title">
        <span>建筑能效对标 TOP8</span>
        <EmsHelpBtn title="能效对标说明">
          <p>按建筑累计电耗排序展示 TOP8，便于快速对比。</p>
          <p>点击「详情」进入完整对标页面。</p>
        </EmsHelpBtn>
      </div>
      <div class="chart-surface-actions">
        <el-button type="primary" link class="link-btn" @click="goBenchmark">详情</el-button>
      </div>
      <AppChart v-if="barBenchmarkOption" class="chart-h chart-h--bar" :option="barBenchmarkOption" />
      <el-empty v-else description="暂无对标数据" :image-size="72">
        <template #image>
          <el-icon class="empty-ico" :size="52"><TrendCharts /></el-icon>
        </template>
        <el-button type="primary" link @click="goBenchmark">前往能效对标</el-button>
      </el-empty>
    </div>
    </template>
  </div>
</template>

<style scoped>
.alert-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: var(--ems-space-md, 16px);
}

.alert-item {
  cursor: pointer;
}

.alert-link {
  font-size: 13px;
  opacity: 0.85;
}

.incident-tip-body {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--ems-text-secondary, #4e5969);
}

.incident-tip-body strong {
  color: var(--ems-text-primary, #1f2329);
  font-weight: 600;
}

.dash-benchmark-card {
  margin-top: var(--ems-space-sm, 8px);
}

.link-btn {
  min-height: 36px;
  padding: 0 8px;
}

.chart-h {
  width: 100%;
  min-height: 260px;
  height: clamp(220px, 32vw, 320px);
}

.chart-h--pie {
  min-height: 280px;
}

.chart-h--bar {
  min-height: 240px;
}

@media (max-width: 768px) {
  .chart-h {
    min-height: 220px;
  }
}

.dash-skeleton-wrap {
  padding: 4px 0 24px;
}

.sk-kpis {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.sk-kpi-cell {
  height: 88px;
  border-radius: 8px;
}

.sk-charts {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 12px;
  margin-top: 12px;
}

.sk-chart-main {
  height: 300px;
  border-radius: 8px;
}

.sk-chart-side {
  height: 300px;
  border-radius: 8px;
}

@media (max-width: 992px) {
  .sk-kpis {
    grid-template-columns: repeat(3, 1fr);
  }
  .sk-charts {
    grid-template-columns: 1fr;
  }
}

.empty-ico {
  color: var(--ems-text-placeholder);
  opacity: 0.85;
}
</style>
