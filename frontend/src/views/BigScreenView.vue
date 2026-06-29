<script setup>
import { computed, onMounted, ref } from 'vue'
import { RefreshRight, ArrowLeft } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import AppChart from '@/components/AppChart.vue'
import AnimatedNumber from '@/components/AnimatedNumber.vue'
import { returnToWorkspace } from '@/utils/workspaceNav'
import * as api from '@/api'
import { usePolling } from '@/composables/usePolling'
import { ElMessage } from 'element-plus'

/* 深色大屏：低对比轴线 + 蓝/绿主色（沿用改版前风格） */
const axisText = '#8b949e'
const axisLine = '#30363d'

const router = useRouter()

const loading = ref(true)
const lastUpdated = ref(null)
const fetchError = ref('')

const buildings = ref({ items: [] })
const period = ref(null)
const benchmark = ref(null)
const timeseries = ref(null)
const forecast = ref(null)
const anomalies = ref(null)
const incidents = ref(null)
const ops = ref(null)
const recordsForWeek = ref(null)

const WEEK_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const WEEK_ORDER = [1, 2, 3, 4, 5, 6, 0]

function fmtNum(n, digits = 0) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(Number(n))
}

function aggregateByWeekday(items) {
  const sumsE = Array(7).fill(0)
  const sumsC = Array(7).fill(0)
  for (const row of items || []) {
    const t = row.monitor_time
    if (!t) continue
    const d = new Date(String(t).replace(/-/g, '/'))
    if (Number.isNaN(d.getTime())) continue
    const wd = d.getDay()
    const e = Number(row.electricity_kwh)
    const c = Number(row.chilledwater_kwh_eq)
    if (!Number.isNaN(e)) sumsE[wd] += e
    if (!Number.isNaN(c)) sumsC[wd] += c
  }
  return {
    labels: WEEK_LABELS,
    elec: WEEK_ORDER.map((i) => Math.round(sumsE[i] * 100) / 100),
    chilled: WEEK_ORDER.map((i) => Math.round(sumsC[i] * 100) / 100),
  }
}

function normRadar(sums) {
  const keys = [
    'electricity_kwh',
    'solar_kwh',
    'water_m3',
    'chilledwater_kwh_eq',
    'hotwater_kwh',
    'relative_humidity_pct',
  ]
  const vals = keys.map((k) => Math.abs(Number(sums?.[k]) || 0))
  const maxv = Math.max(...vals, 1e-6)
  return vals.map((v) => Math.min(100, (v / maxv) * 100))
}

const firstBuildingId = computed(() => {
  const it = buildings.value?.items?.[0]
  if (!it) return ''
  return it.building_id ?? it.id ?? ''
})

const kpis = computed(() => {
  const sums = period.value?.sums ?? {}
  const elec = Number(sums.electricity_kwh)
  const pend = incidents.value?.pending ?? 0
  const ar = anomalies.value?.ratio
  const nBuild = buildings.value?.items?.length ?? 0
  const pctNum = ar != null && !Number.isNaN(Number(ar)) ? Number(ar) * 100 : null

  return [
    {
      label: '累计市电(库内)',
      animValue: Number.isFinite(elec) ? elec : null,
      animDigits: 0,
      unit: 'kWh',
      tag: 'normal',
    },
    {
      label: '待处理工单',
      animValue: pend,
      animDigits: 0,
      unit: '条',
      tag: pend > 0 ? 'warn' : 'ok',
    },
    {
      label: '用电异常占比',
      animValue: pctNum,
      animDigits: 2,
      unit: '%',
      tag: ar != null && ar > 0.1 ? 'danger' : ar > 0.05 ? 'warn' : 'ok',
    },
    {
      label: '监测建筑数',
      animValue: nBuild,
      animDigits: 0,
      unit: '栋',
      tag: 'normal',
    },
  ]
})

const barGroupedOption = computed(() => {
  const agg = recordsForWeek.value?.items?.length
    ? aggregateByWeekday(recordsForWeek.value.items)
    : null
  const hasData = agg && agg.elec.some((v) => v > 0)
  const elec = hasData ? agg.elec : [0, 0, 0, 0, 0, 0, 0]
  const chilled = hasData ? agg.chilled : [0, 0, 0, 0, 0, 0, 0]
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', textStyle: { color: '#c9d1d9' } },
    legend: {
      data: ['市电累计', '冷量当量累计'],
      textStyle: { color: axisText },
      top: 0,
    },
    grid: { left: 48, right: 24, top: 40, bottom: 32 },
    xAxis: {
      type: 'category',
      data: WEEK_LABELS,
      axisLine: { lineStyle: { color: axisLine } },
      axisLabel: { color: axisText, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 'kWh',
      nameTextStyle: { color: axisText, fontSize: 11 },
      axisLine: { show: false },
      splitLine: { show: false },
      axisLabel: { color: axisText },
    },
    series: [
      {
        name: '市电累计',
        type: 'bar',
        barMaxWidth: 18,
        data: elec,
        itemStyle: {
          color: '#1890ff',
          borderRadius: [4, 4, 0, 0],
        },
      },
      {
        name: '冷量当量累计',
        type: 'bar',
        barMaxWidth: 18,
        data: chilled,
        itemStyle: {
          color: '#52c41a',
          borderRadius: [4, 4, 0, 0],
        },
      },
    ],
  }
})

const lineAreaOption = computed(() => {
  let labels = timeseries.value?.labels ?? []
  let values = (timeseries.value?.values ?? []).map((v) => (v == null ? null : Number(v)))
  if (!labels.length && forecast.value?.labels?.length) {
    labels = forecast.value.labels
    values = (forecast.value.values ?? []).map((v) => Number(v))
  }
  const unit = timeseries.value?.unit_hint ?? 'kWh/h'
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', textStyle: { color: '#c9d1d9' } },
    grid: { left: 52, right: 20, top: 28, bottom: labels.length > 40 ? 40 : 28 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels.length ? labels : ['—'],
      axisLine: { lineStyle: { color: axisLine } },
      axisLabel: { color: axisText, fontSize: 10, rotate: labels.length > 36 ? 35 : 0 },
    },
    yAxis: {
      type: 'value',
      name: unit,
      nameTextStyle: { color: axisText },
      axisLine: { show: false },
      splitLine: { show: false },
      axisLabel: { color: axisText },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: values.length ? values : [0],
        lineStyle: { width: 2, color: '#58a6ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(88, 166, 255, 0.22)' },
              { offset: 1, color: 'rgba(13, 17, 23, 0.02)' },
            ],
          },
        },
      },
    ],
  }
})

const gaugeTripleOption = computed(() => {
  const items = benchmark.value?.items ?? []
  const topScore = items.length ? Number(items[0].score) || 0 : 0
  const ratio = anomalies.value?.ratio != null ? Number(anomalies.value.ratio) : 0
  const health = Math.max(0, Math.min(100, (1 - ratio) * 100))
  const ind = ops.value?.indicators ?? {}
  const su = ind.su != null ? Number(ind.su) : 0.5
  const g3 = Math.round(Math.min(100, su * 100))

  return {
    backgroundColor: 'transparent',
    series: [
      {
        type: 'gauge',
        center: ['18%', '55%'],
        radius: '55%',
        min: 0,
        max: 100,
        splitNumber: 5,
        axisLine: {
          lineStyle: {
            width: 10,
            color: [
              [0.3, '#52c41a'],
              [0.7, '#faad14'],
              [1, '#ff4d4f'],
            ],
          },
        },
        pointer: { itemStyle: { color: '#58a6ff' } },
        axisTick: { distance: -10, length: 6, lineStyle: { color: '#4a6a8a' } },
        splitLine: { distance: -12, length: 12, lineStyle: { color: '#4a6a8a' } },
        axisLabel: { color: axisText, distance: 14, fontSize: 10 },
        detail: {
          valueAnimation: true,
          formatter: '{value}',
          color: '#e6f4ff',
          fontSize: 14,
          offsetCenter: [0, '70%'],
        },
        title: { offsetCenter: [0, '95%'], color: axisText, fontSize: 11 },
        data: [{ value: Math.round(topScore), name: '对标得分' }],
      },
      {
        type: 'gauge',
        center: ['50%', '55%'],
        radius: '55%',
        min: 0,
        max: 100,
        axisLine: {
          lineStyle: {
            width: 10,
            color: [
              [0.4, '#1890ff'],
              [0.8, '#69c0ff'],
              [1, '#52c41a'],
            ],
          },
        },
        pointer: { itemStyle: { color: '#69c0ff' } },
        axisTick: { distance: -10, length: 6, lineStyle: { color: '#4a6a8a' } },
        splitLine: { distance: -12, length: 12, lineStyle: { color: '#4a6a8a' } },
        axisLabel: { color: axisText, distance: 14, fontSize: 10 },
        detail: {
          valueAnimation: true,
          formatter: '{value}',
          color: '#e6f4ff',
          fontSize: 14,
          offsetCenter: [0, '70%'],
        },
        title: { offsetCenter: [0, '95%'], color: axisText, fontSize: 11 },
        data: [{ value: Math.round(health), name: '用电健康度' }],
      },
      {
        type: 'gauge',
        center: ['82%', '55%'],
        radius: '55%',
        min: 0,
        max: 100,
        axisLine: {
          lineStyle: {
            width: 10,
            color: [
              [0.5, '#13c2c2'],
              [1, '#006d75'],
            ],
          },
        },
        pointer: { itemStyle: { color: '#36cfc9' } },
        axisTick: { distance: -10, length: 6, lineStyle: { color: '#4a6a8a' } },
        splitLine: { distance: -12, length: 12, lineStyle: { color: '#4a6a8a' } },
        axisLabel: { color: axisText, distance: 14, fontSize: 10 },
        detail: {
          valueAnimation: true,
          formatter: '{value}',
          color: '#e6f4ff',
          fontSize: 14,
          offsetCenter: [0, '70%'],
        },
        title: { offsetCenter: [0, '95%'], color: axisText, fontSize: 11 },
        data: [{ value: g3, name: 'SU(演示)' }],
      },
    ],
  }
})

const radarOption = computed(() => {
  const sums = period.value?.sums ?? {}
  const v = normRadar(sums)
  const ar = anomalies.value?.ratio != null ? Number(anomalies.value.ratio) : 0
  v[5] = Math.max(0, Math.min(100, (1 - ar) * 100))
  const indicators = [
    { name: '市电', max: 100 },
    { name: '光伏', max: 100 },
    { name: '用水', max: 100 },
    { name: '冷量', max: 100 },
    { name: '热水', max: 100 },
    { name: '健康度', max: 100 },
  ]
  return {
    backgroundColor: 'transparent',
    tooltip: { textStyle: { color: '#c9d1d9' } },
    radar: {
      indicator: indicators,
      splitArea: { areaStyle: { color: ['rgba(48, 54, 61, 0.35)', 'rgba(22, 27, 34, 0.25)'] } },
      axisName: { color: axisText, fontSize: 11 },
      splitLine: { lineStyle: { color: axisLine } },
      axisLine: { lineStyle: { color: axisLine } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: v,
            name: '全库归一',
            areaStyle: { color: 'rgba(88, 166, 255, 0.2)' },
            lineStyle: { color: '#58a6ff', width: 2 },
            itemStyle: { color: '#58a6ff' },
          },
        ],
      },
    ],
  }
})

const donutOption = computed(() => {
  const sums = period.value?.sums ?? {}
  const parts = [
    { value: Number(sums.electricity_kwh) || 0, name: '市电', itemStyle: { color: '#1890ff' } },
    { value: Number(sums.solar_kwh) || 0, name: '光伏', itemStyle: { color: '#52c41a' } },
    { value: Number(sums.chilledwater_kwh_eq) || 0, name: '冷量', itemStyle: { color: '#69c0ff' } },
    { value: Number(sums.hotwater_kwh) || 0, name: '热水', itemStyle: { color: '#faad14' } },
  ].filter((p) => p.value > 0)
  if (!parts.length) {
    return {
      backgroundColor: 'transparent',
      title: {
        text: '暂无累计分项',
        left: 'center',
        top: 'center',
        textStyle: { color: axisText, fontSize: 13 },
      },
    }
  }
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', textStyle: { color: '#c9d1d9' } },
    legend: {
      orient: 'vertical',
      right: 8,
      top: 'center',
      textStyle: { color: axisText, fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['40%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: '#0d1117', borderWidth: 2 },
        label: { color: '#c9d1d9', fontSize: 11 },
        data: parts,
      },
    ],
  }
})

const hBarOption = computed(() => {
  const items = (benchmark.value?.items ?? []).slice(0, 5)
  const names = items.map((it) => String(it.building_id ?? '').slice(0, 14))
  const vals = items.map((it) => Number(it.total_electricity_kwh) || 0)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, textStyle: { color: '#c9d1d9' } },
    grid: { left: 120, right: 48, top: 16, bottom: 16 },
    xAxis: {
      type: 'value',
      name: 'kWh',
      nameTextStyle: { color: axisText },
      axisLine: { show: false },
      splitLine: { show: false },
      axisLabel: { color: axisText },
    },
    yAxis: {
      type: 'category',
      data: names.length ? names : ['—'],
      axisLine: { lineStyle: { color: axisLine } },
      axisLabel: { color: axisText, fontSize: 11 },
    },
    series: [
      {
        type: 'bar',
        data: vals.length ? vals : [0],
        barMaxWidth: 16,
        itemStyle: {
          color: '#1890ff',
          borderRadius: [0, 4, 4, 0],
        },
      },
    ],
  }
})

const scatterMapLikeOption = computed(() => {
  const items = benchmark.value?.items ?? []
  const data = items.slice(0, 12).map((it, i) => {
    const rank = Number(it.rank) || i + 1
    const score = Number(it.score) || 0
    const te = Number(it.total_electricity_kwh) || 0
    const x = 10 + rank * 6.5
    const y = Math.min(95, Math.max(5, score))
    return [x, y, String(it.building_id).slice(0, 12), te]
  })
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        const arr = Array.isArray(p.value) ? p.value : p.data
        if (!Array.isArray(arr)) return ''
        return `${arr[2]}<br/>Y=${arr[1]} · 总电 ${fmtNum(arr[3], 0)} kWh`
      },
      textStyle: { color: '#c9d1d9' },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 32 },
    xAxis: {
      type: 'value',
      name: '名次序',
      nameTextStyle: { color: axisText },
      min: 0,
      axisLine: { show: false },
      splitLine: { show: false },
      axisLabel: { color: axisText },
    },
    yAxis: {
      type: 'value',
      name: '得分',
      max: 100,
      nameTextStyle: { color: axisText },
      axisLine: { show: false },
      splitLine: { show: false },
      axisLabel: { color: axisText },
    },
    series: [
      {
        type: 'effectScatter',
        symbolSize: (val) => {
          const te = Array.isArray(val) ? val[3] : 0
          return 10 + Math.min(22, Math.sqrt(Math.max(te, 0) / 2000))
        },
        rippleEffect: { brushType: 'stroke', scale: 2.5 },
        itemStyle: {
          color: '#58a6ff',
          shadowBlur: 6,
          shadowColor: 'rgba(88, 166, 255, 0.25)',
        },
        data: data.length ? data : [[50, 50, '无数据', 0]],
      },
    ],
  }
})

async function loadAll({ silent = false } = {}) {
  if (!silent) loading.value = true
  fetchError.value = ''
  try {
    const b = await api.getBuildings().catch(() => ({ items: [] }))
    buildings.value = b
    const bid = b.items?.[0]?.building_id ?? b.items?.[0]?.id ?? ''

    const [
      per,
      bench,
      ano,
      inc,
      ts,
      fc,
      op,
      rec,
    ] = await Promise.all([
      api.getStatsPeriod({}).catch(() => null),
      api.getBenchmarkScoreboard({ top_n: 12 }).catch(() => null),
      api.getStatsAnomalies({ z_threshold: 3 }).catch(() => null),
      api.getIncidentsSummary().catch(() => null),
      bid
        ? api
            .getStatsTimeseries({
              building_id: bid,
              metric: 'electricity_kwh',
              limit: 500,
            })
            .catch(() => null)
        : Promise.resolve(null),
      api.getV2ForecastEnergy({ horizon_hours: 24 }).catch(() => null),
      api.getV2OpsIndicators().catch(() => null),
      api.getEnergyRecords({ limit: 8000, offset: 0, sort_by: 'monitor_time', sort_order: 'desc' }).catch(() => null),
    ])

    period.value = per
    benchmark.value = bench
    anomalies.value = ano
    incidents.value = inc
    timeseries.value = ts
    forecast.value = fc
    ops.value = op
    recordsForWeek.value = rec

    lastUpdated.value = new Date()
  } catch (e) {
    fetchError.value = e.message ?? String(e)
    if (!silent) ElMessage.error(fetchError.value)
  } finally {
    if (!silent) loading.value = false
  }
}

onMounted(() => loadAll({ silent: false }))
usePolling(() => loadAll({ silent: true }), 60_000)
</script>

<template>
  <div v-loading="loading" class="screen-root">
    <header class="screen-header">
      <div class="screen-head-row">
        <div>
          <h1 class="screen-title">建筑能源数据大屏</h1>
          <p class="screen-sub">
            数据来源：后端 API（能耗 CSV 聚合）·
            <template v-if="lastUpdated">更新 {{ lastUpdated.toLocaleString('zh-CN') }}</template>
            <template v-else>加载中…</template>
          </p>
          <p v-if="fetchError" class="screen-err">{{ fetchError }}</p>
        </div>
        <div class="screen-head-actions">
          <el-button round :icon="ArrowLeft" @click="returnToWorkspace(router)">返回工作台</el-button>
          <el-tooltip content="重新拉取全部接口" placement="left">
            <el-button
              type="primary"
              class="btn-refresh"
              :loading="loading"
              :icon="RefreshRight"
              @click="loadAll({ silent: false })"
            >
              刷新
            </el-button>
          </el-tooltip>
        </div>
      </div>
    </header>

    <p v-if="firstBuildingId" class="hint-bid">时序默认建筑：{{ firstBuildingId }}</p>

    <el-row :gutter="12" class="kpi-row">
      <el-col v-for="(k, i) in kpis" :key="i" :xs="12" :sm="12" :md="6">
        <div class="kpi-tile" :class="`kpi-tile--${k.tag}`">
          <div class="kpi-label">{{ k.label }}</div>
          <div class="kpi-num">
            <template v-if="k.animValue != null && !Number.isNaN(k.animValue)">
              <AnimatedNumber
                :key="`${i}-${lastUpdated?.getTime() ?? 0}`"
                :value="k.animValue"
                :digits="k.animDigits"
                :duration="720"
              />
            </template>
            <template v-else>—</template>
            <span class="kpi-unit">{{ k.unit }}</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="12" class="panel-row">
      <el-col :xs="24" :lg="12">
        <div class="panel">
          <div class="panel-title">按星期累计 · 市电 / 冷量（全库抽样小时行聚合）</div>
          <AppChart class="chart-box" :option="barGroupedOption" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="12">
        <div class="panel">
          <div class="panel-title">
            市电时序 / 预测
            <span class="panel-hint">{{ timeseries?.labels?.length ? '时序' : forecast?.labels?.length ? '预测' : '无' }}</span>
          </div>
          <AppChart class="chart-box" :option="lineAreaOption" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="12" class="panel-row">
      <el-col :xs="24" :lg="14">
        <div class="panel panel--tall">
          <div class="panel-title">对标得分 · 健康度 · SU(演示)</div>
          <AppChart class="chart-box chart-box--gauge" :option="gaugeTripleOption" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="10">
        <div class="panel panel--tall">
          <div class="panel-title">分项归一雷达（末维为异常 inverse）</div>
          <AppChart class="chart-box" :option="radarOption" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="12" class="panel-row">
      <el-col :xs="24" :md="10">
        <div class="panel">
          <div class="panel-title">全库累计构成（period.sums）</div>
          <AppChart class="chart-box chart-box--pie" :option="donutOption" />
        </div>
      </el-col>
      <el-col :xs="24" :md="14">
        <div class="panel">
          <div class="panel-title">能效对标 TOP5 · 总电耗</div>
          <AppChart class="chart-box chart-box--hbar" :option="hBarOption" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="12" class="panel-row panel-row--last">
      <el-col :span="24">
        <div class="panel">
          <div class="panel-title">对标分布（得分–总电耗，气泡大小）</div>
          <AppChart class="chart-box chart-box--scatter" :option="scatterMapLikeOption" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.screen-root {
  margin: 0;
  min-height: 100vh;
  padding: 16px 20px 24px;
  box-sizing: border-box;
  background: #0d1117;
  color: #c9d1d9;
}

.screen-header {
  margin-bottom: 16px;
  padding: 12px 0;
  border-bottom: 1px solid #30363d;
  box-shadow: none;
}

.screen-head-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.screen-head-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.screen-title {
  margin: 0;
  text-align: left;
  font-size: clamp(20px, 3vw, 26px);
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #e6edf3;
}

.screen-sub {
  margin: 8px 0 0;
  font-size: 12px;
  color: #8b949e;
}

.screen-err {
  margin: 8px 0 0;
  font-size: 12px;
  color: #ff7875;
}

.btn-refresh {
  min-height: 40px;
}

.hint-bid {
  font-size: 12px;
  color: #6e7681;
  margin: 0 0 12px;
}

.kpi-row {
  margin-bottom: 12px;
}

.kpi-tile {
  padding: 14px 16px;
  border-radius: 8px;
  border: 1px solid #30363d;
  background: #161b22;
  box-shadow: none;
}

.kpi-tile--ok {
  border-left: 3px solid #52c41a;
}
.kpi-tile--warn {
  border-left: 3px solid #faad14;
}
.kpi-tile--danger {
  border-left: 3px solid #ff4d4f;
}
.kpi-tile--normal {
  border-left: 3px solid #1890ff;
}

.kpi-label {
  font-size: 12px;
  color: #8b949e;
  margin-bottom: 6px;
}

.kpi-num {
  font-size: 22px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #e6edf3;
}

.kpi-unit {
  font-size: 12px;
  font-weight: 400;
  margin-left: 4px;
  color: #6e7681;
}

.panel-row {
  margin-bottom: 12px;
}

.panel-row--last {
  margin-bottom: 0;
}

.panel {
  height: 100%;
  min-height: 280px;
  padding: 12px 14px 14px;
  border-radius: 8px;
  border: 1px solid #30363d;
  background: #161b22;
  box-shadow: none;
}

.panel--tall {
  min-height: 320px;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #c9d1d9;
  margin-bottom: 8px;
  padding-left: 8px;
  border-left: 3px solid #1890ff;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-hint {
  font-size: 11px;
  font-weight: 400;
  color: #6e7681;
}

.chart-box {
  width: 100%;
  min-height: 240px;
  height: 260px;
}

.chart-box--gauge {
  min-height: 260px;
  height: 280px;
}

.chart-box--pie {
  min-height: 260px;
  height: 280px;
}

.chart-box--hbar {
  min-height: 220px;
  height: 260px;
}

.chart-box--scatter {
  min-height: 260px;
  height: 280px;
}

@media (max-width: 768px) {
  .screen-root {
    margin: -12px;
    padding: 12px;
  }

  .chart-box,
  .chart-box--gauge,
  .chart-box--pie {
    height: 240px;
  }
}
</style>
