<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import AppChart from '@/components/AppChart.vue'
import EmsDrawer from '@/components/EmsDrawer.vue'
import EmsHelpBtn from '@/components/EmsHelpBtn.vue'
import * as api from '@/api'
import { ElMessage } from 'element-plus'
import { buildDonutRowFromSums, comboBarLineOption, operationCurveOption } from '@/utils/myemsCharts'

const buildings = ref([])
const buildingId = ref('')
const compareType = ref('none')
const timeSpan = ref('hour')
const dateRange = ref(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const records = ref(null)
const loading = ref(false)
/** 避免首屏 loadBuildings 设置 buildingId 时触发重复请求 */
const filtersReady = ref(false)

const periodSummary = ref(null)
const anomaliesKpi = ref(null)
const incidentsSummary = ref(null)
const tsChart = ref(null)
const tsChartCompare = ref(null)
const benchmarkBoard = ref(null)

const sortBy = ref('monitor_time')
const sortOrder = ref('asc')

const filterDrawerVisible = ref(false)
const detailDrawerVisible = ref(false)
const detailRow = ref(null)

const tableData = computed(() => records.value?.items ?? [])
const columns = computed(() => {
  const row = tableData.value[0]
  if (!row || typeof row !== 'object') return []
  return Object.keys(row)
})

const chartBuildingId = computed(() => {
  if (buildingId.value) return buildingId.value
  const b = buildings.value[0]
  return b?.building_id ?? b?.id ?? ''
})

const tableHeight = computed(() => {
  if (typeof window !== 'undefined' && window.innerWidth < 768) return 320
  return 420
})

const dateError = ref('')

const donutOptions = computed(() =>
  buildDonutRowFromSums(periodSummary.value?.sums, periodSummary.value?.means),
)

/** 对标样本：各建筑总电均值 / 当前时序点数 → 与小时值同量纲的参考线 */
const benchmarkPeerHourly = computed(() => {
  const items = benchmarkBoard.value?.items ?? []
  const labels = tsChart.value?.labels ?? []
  if (!items.length || !labels.length) return null
  const sumTot = items.reduce((a, x) => a + (Number(x.total_electricity_kwh) || 0), 0)
  const avgBuilding = sumTot / items.length
  return avgBuilding / labels.length
})

const comboOption = computed(() => {
  const labels = tsChart.value?.labels ?? []
  const raw = tsChart.value?.values ?? []
  const values = raw.map((v) => (v == null ? 0 : Number(v)))
  let compareValues = null
  if (compareType.value === 'week_prev' && tsChartCompare.value?.values?.length) {
    compareValues = tsChartCompare.value.values.map((v) => (v == null ? 0 : Number(v)))
  }
  return comboBarLineOption(labels, values, {
    compareValues,
    benchmarkY: benchmarkPeerHourly.value,
    compareLabel: '上周同期',
  })
})

const curveOption = computed(() => {
  const labels = tsChart.value?.labels ?? []
  const raw = tsChart.value?.values ?? []
  const values = raw.map((v) => (v == null ? 0 : Number(v)))
  return operationCurveOption(labels, values, { benchmarkY: benchmarkPeerHourly.value })
})

const kpis = computed(() => {
  const sums = periodSummary.value?.sums ?? {}
  const elec = Number(sums.electricity_kwh)
  const water = Number(sums.water_m3)
  const rows = periodSummary.value?.rows ?? 0
  const ar = anomaliesKpi.value?.ratio
  const pct = ar != null ? (Number(ar) * 100).toFixed(2) : '—'
  const trendUp = ar != null && ar > 0.05
  const serious = ar != null && ar > 0.1
  return [
    {
      label: '市电累计',
      value: Number.isFinite(elec) ? elec.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) : '—',
      unit: 'kWh',
      trend: '较异常阈值',
      trendDir: trendUp ? 'up' : 'down',
      trendText: trendUp ? `异常占比 ${pct}%` : `异常占比 ${pct}%`,
      kpiClass: serious ? 'myems-kpi-card--accent-danger' : trendUp ? 'myems-kpi-card--accent-warn' : '',
    },
    {
      label: '用水累计',
      value: Number.isFinite(water) ? water.toLocaleString('zh-CN', { maximumFractionDigits: 1 }) : '—',
      unit: 'm³',
      trend: '筛选期内',
      trendDir: 'neutral',
      trendText: '合计',
      kpiClass: '',
    },
    {
      label: '数据行数',
      value: String(rows),
      unit: '行',
      trend: '时段内',
      trendDir: 'neutral',
      trendText: '小时粒度',
      kpiClass: '',
    },
    {
      label: '待处理工单',
      value: String(incidentsSummary.value?.pending ?? '—'),
      unit: '条',
      trend: '运维',
      trendDir: 'neutral',
      trendText: '实时',
      kpiClass: '',
    },
  ]
})

function headerCellStyle() {
  return {
    background: '#fafafa',
    color: 'var(--ems-text-primary, #1f2329)',
    fontWeight: 600,
    borderBottom: '1px solid #e4e7ed',
  }
}

const energyColumnKeys = computed(() => {
  const cols = columns.value
  return cols.filter(
    (c) =>
      c.includes('kwh') ||
      c.includes('electricity') ||
      c === 'water_m3' ||
      (c.includes('water') && c !== 'monitor_time'),
  )
})

const colMaxForPage = computed(() => {
  const m = {}
  for (const col of energyColumnKeys.value) {
    let max = 0
    for (const row of tableData.value) {
      const v = Number(row[col])
      if (!Number.isNaN(v)) max = Math.max(max, Math.abs(v))
    }
    m[col] = max || 1
  }
  return m
})

function cellStyleWithSpark({ row, column }) {
  const base = { padding: '10px 0' }
  const prop = column.property
  if (!prop || !energyColumnKeys.value.includes(prop)) return base
  const v = Number(row[prop])
  if (Number.isNaN(v)) return base
  const max = colMaxForPage.value[prop] || 1
  const pct = Math.min(100, Math.round((Math.abs(v) / max) * 100))
  return {
    ...base,
    background: `linear-gradient(90deg, rgba(24, 144, 255, 0.15) ${pct}%, transparent ${pct}%)`,
  }
}

function summaryMethod({ columns: cols, data }) {
  return cols.map((col, index) => {
    if (index === 0) return '合计'
    const prop = col.property
    if (!prop) return ''
    const nums = data.map((row) => Number(row[prop])).filter((n) => !Number.isNaN(n))
    if (!nums.length) return '—'
    const s = nums.reduce((a, b) => a + b, 0)
    return Number.isInteger(s) ? String(s) : s.toFixed(2)
  })
}

function validateRange() {
  dateError.value = ''
  if (!dateRange.value || !Array.isArray(dateRange.value) || dateRange.value.length !== 2) {
    return true
  }
  const [a, b] = dateRange.value
  if (a && b && new Date(a).getTime() > new Date(b).getTime()) {
    dateError.value = '开始时间不能晚于结束时间'
    return false
  }
  return true
}

function rangeToParams() {
  if (!dateRange.value || !Array.isArray(dateRange.value) || dateRange.value.length !== 2) {
    return { time_from: undefined, time_to: undefined }
  }
  const [start, end] = dateRange.value
  if (!start || !end) return { time_from: undefined, time_to: undefined }
  return { time_from: start, time_to: end }
}

/** 将统计期整体平移若干天（用于「上周同期」对比） */
function shiftDaysRange(timeFrom, timeTo, days) {
  const parse = (s) => new Date(String(s).replace(' ', 'T'))
  const df = parse(timeFrom)
  const dt = parse(timeTo)
  if (Number.isNaN(df.getTime()) || Number.isNaN(dt.getTime())) {
    return { time_from: undefined, time_to: undefined }
  }
  df.setDate(df.getDate() + days)
  dt.setDate(dt.getDate() + days)
  const fmt = (d) => {
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  }
  return { time_from: fmt(df), time_to: fmt(dt) }
}

async function loadBuildings() {
  try {
    const data = await api.getBuildings()
    buildings.value = data.items ?? []
    if (!buildingId.value && buildings.value.length) {
      buildingId.value = buildings.value[0].building_id ?? buildings.value[0].id ?? ''
    }
  } catch (e) {
    ElMessage.error(e.message ?? '加载建筑列表失败')
  }
}

async function loadContext() {
  const { time_from, time_to } = rangeToParams()
  const params = {}
  if (buildingId.value) params.building_id = buildingId.value
  if (time_from) params.time_from = time_from
  if (time_to) params.time_to = time_to

  const benchParams = { top_n: 24 }
  if (time_from) benchParams.time_from = time_from
  if (time_to) benchParams.time_to = time_to

  const [per, ano, inc, bench] = await Promise.all([
    api.getStatsPeriod(params).catch(() => null),
    api.getStatsAnomalies({ ...params, z_threshold: 3 }).catch(() => null),
    api.getIncidentsSummary().catch(() => null),
    api.getBenchmarkScoreboard(benchParams).catch(() => null),
  ])
  periodSummary.value = per
  anomaliesKpi.value = ano
  incidentsSummary.value = inc
  benchmarkBoard.value = bench

  const bid = chartBuildingId.value
  if (bid) {
    tsChart.value = await api
      .getStatsTimeseries({
        building_id: bid,
        metric: 'electricity_kwh',
        limit: 500,
        ...(time_from ? { time_from } : {}),
        ...(time_to ? { time_to } : {}),
      })
      .catch(() => null)

    if (compareType.value === 'week_prev' && time_from && time_to) {
      const prev = shiftDaysRange(time_from, time_to, -7)
      if (prev.time_from && prev.time_to) {
        tsChartCompare.value = await api
          .getStatsTimeseries({
            building_id: bid,
            metric: 'electricity_kwh',
            limit: 500,
            time_from: prev.time_from,
            time_to: prev.time_to,
          })
          .catch(() => null)
      } else {
        tsChartCompare.value = null
      }
    } else {
      tsChartCompare.value = null
    }
  } else {
    tsChart.value = null
    tsChartCompare.value = null
  }
}

async function loadRecords({ notifySuccess = false } = {}) {
  if (!validateRange()) {
    ElMessage.warning(dateError.value)
    return
  }
  loading.value = true
  try {
    const { time_from, time_to } = rangeToParams()
    const offset = (page.value - 1) * pageSize.value
    const params = {
      limit: pageSize.value,
      offset,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    }
    if (buildingId.value) params.building_id = buildingId.value
    if (time_from) params.time_from = time_from
    if (time_to) params.time_to = time_to

    const data = await api.getEnergyRecords(params)
    records.value = data
    total.value = Number(data.total ?? 0)

    if (notifySuccess) {
      ElMessage.success({
        message: `已加载 ${data.items?.length ?? 0} 条 / 共 ${total.value} 条`,
        duration: 2000,
        showClose: true,
      })
    }
  } catch (e) {
    ElMessage.error(e.message ?? '查询失败')
  } finally {
    loading.value = false
  }
}

async function applyToolbarFilters() {
  if (!validateRange()) {
    ElMessage.warning(dateError.value)
    return
  }
  page.value = 1
  loading.value = true
  try {
    await loadContext()
    await loadRecords({ notifySuccess: false })
  } finally {
    loading.value = false
  }
}

function onSortChange({ prop, order }) {
  if (!prop || !order) {
    sortBy.value = 'monitor_time'
    sortOrder.value = 'asc'
  } else {
    sortBy.value = prop
    sortOrder.value = order === 'descending' ? 'desc' : 'asc'
  }
  page.value = 1
  loadRecords({ notifySuccess: true })
}

function onPageChange() {
  loadRecords({ notifySuccess: false })
}

function onPageSizeChange() {
  page.value = 1
  loadRecords({ notifySuccess: false })
}

function onRowClick(row) {
  detailRow.value = row
  detailDrawerVisible.value = true
}

function rowClassName() {
  return 'energy-row-clickable'
}

onMounted(async () => {
  await loadBuildings()
  await loadContext()
  await loadRecords({ notifySuccess: false })
  filtersReady.value = true
})

watch(
  [buildingId, dateRange, compareType],
  async () => {
    if (!filtersReady.value) return
    await applyToolbarFilters()
  },
  { deep: true },
)
</script>

<template>
  <div class="myems-page energy-view">
    <div class="energy-toolbar-bar">
      <div class="energy-toolbar-summary">
        <el-tag v-if="buildingId" effect="plain" round>{{ buildingId }}</el-tag>
        <el-tag v-else effect="plain" round type="info">全部建筑</el-tag>
        <el-tag v-if="dateRange?.length === 2" effect="plain" round type="info">
          {{ dateRange[0]?.slice(0, 16) }} ~ {{ dateRange[1]?.slice(0, 16) }}
        </el-tag>
      </div>
      <el-button type="primary" round @click="filterDrawerVisible = true">筛选条件</el-button>
    </div>

    <EmsDrawer v-model="filterDrawerVisible" title="筛选与查询" size="520px">
      <el-form label-width="0" class="toolbar-form" @submit.prevent>
        <el-form-item>
          <el-select
            v-model="buildingId"
            clearable
            placeholder="空间 · 全部建筑"
            class="w-full"
            filterable
          >
            <el-option
              v-for="b in buildings"
              :key="JSON.stringify(b)"
              :label="b.building_id ?? b.name ?? String(b)"
              :value="b.building_id ?? b.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-select v-model="compareType" placeholder="对比" class="w-full">
            <el-option label="无对比" value="none" />
            <el-option label="上周同期" value="week_prev" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-select v-model="timeSpan" placeholder="粒度" class="w-full">
            <el-option label="小时" value="hour" />
            <el-option label="日(占位)" value="day" disabled />
          </el-select>
        </el-form-item>
        <el-form-item :error="dateError">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="统计期 · 开始"
            end-placeholder="统计期 · 结束"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
            class="w-full"
            @change="validateRange"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button round @click="filterDrawerVisible = false">关闭</el-button>
        <el-button type="primary" round @click="filterDrawerVisible = false">应用筛选</el-button>
      </template>
    </EmsDrawer>

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
        <span>分项占比</span>
        <EmsHelpBtn title="分项占比说明">
          <p>基于当前筛选时段的汇总字段 <code>sums</code> 计算各分项占比。</p>
        </EmsHelpBtn>
      </div>
      <el-row :gutter="12" class="myems-donut-grid">
        <el-col v-for="(opt, idx) in donutOptions" :key="idx" :xs="24" :sm="12" :md="6">
          <AppChart class="chart-mini" :option="opt" />
        </el-col>
      </el-row>
    </div>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>报告期用电 · 柱线组合</span>
        <EmsHelpBtn title="柱线组合图说明">
          <p>建筑：{{ chartBuildingId || '—' }}</p>
          <p>紫虚线为对标样本均时参考线。</p>
          <p v-if="compareType === 'week_prev'">绿虚线为上周同期对比曲线。</p>
        </EmsHelpBtn>
      </div>
      <AppChart v-if="tsChart?.labels?.length" class="chart-combo" :option="comboOption" />
      <el-empty v-else description="请选择空间或等待时序数据；变更顶部筛选后将自动加载" :image-size="72" />
    </div>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>运行曲线</span>
        <EmsHelpBtn title="运行曲线说明">
          <p>纵轴为市电用量，单位 kWh/h。</p>
        </EmsHelpBtn>
      </div>
      <AppChart v-if="tsChart?.labels?.length" class="chart-curve" :option="curveOption" />
      <el-empty v-else description="无时序数据" :image-size="72" />
    </div>

    <div class="myems-section">
      <div class="myems-section-head">
        <span>详细数据</span>
        <el-tag v-if="total" effect="plain" round size="small">{{ total }} 条</el-tag>
        <EmsHelpBtn title="明细表说明">
          <p>点击任意行可在右侧抽屉查看完整字段。</p>
          <p>表底汇总行对数值列求和。</p>
        </EmsHelpBtn>
      </div>
      <div class="table-wrap">
        <el-table
          v-loading="loading"
          :data="tableData"
          class="data-table data-table--borderless energy-table"
          :height="tableHeight"
          :header-cell-style="headerCellStyle"
          :cell-style="cellStyleWithSpark"
          :row-class-name="rowClassName"
          show-summary
          :summary-method="summaryMethod"
          :default-sort="{ prop: 'monitor_time', order: 'ascending' }"
          @sort-change="onSortChange"
          @row-click="onRowClick"
        >
          <el-table-column
            v-for="col in columns"
            :key="col"
            :prop="col"
            :label="col"
            :min-width="
              col === 'monitor_time' ? 168 : col.includes('electricity') || col.includes('kwh') ? 130 : 120
            "
            sortable="custom"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <span
                v-if="col === 'electricity_kwh' || (col.includes('kwh') && col !== 'monitor_time')"
                class="num-highlight"
              >
                {{ row[col] }}
              </span>
              <span v-else>{{ row[col] }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="pager-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          :disabled="loading"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </div>

    <EmsDrawer v-model="detailDrawerVisible" title="记录详情" size="420px">
      <template v-if="detailRow">
        <el-descriptions :column="1" border size="small" class="energy-detail-desc">
          <el-descriptions-item
            v-for="col in columns"
            :key="col"
            :label="col"
          >
            {{ detailRow[col] ?? '—' }}
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else description="未选择记录" :image-size="64" />
      <template #footer>
        <el-button round @click="detailDrawerVisible = false">关闭</el-button>
      </template>
    </EmsDrawer>
  </div>
</template>

<style scoped>
.energy-toolbar-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding: 12px 16px;
  background: var(--feishu-surface, #fff);
  border-radius: var(--feishu-radius-md, 12px);
  box-shadow: var(--feishu-shadow-sm, 0 2px 8px rgba(31, 35, 41, 0.06));
}

.energy-toolbar-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(.energy-row-clickable) {
  cursor: pointer;
}

.energy-detail-desc {
  border-radius: var(--feishu-radius-sm, 8px);
  overflow: hidden;
}

.w-full {
  width: 100%;
}

.toolbar-form {
  margin: 0;
}

.label-cal {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.section-hint {
  font-size: 12px;
  font-weight: 400;
  color: rgba(0, 0, 0, 0.35);
}

.chart-combo,
.chart-curve {
  width: 100%;
  min-height: 300px;
  height: 340px;
}

.chart-mini {
  min-height: 230px;
  height: 230px;
}

.table-wrap {
  overflow-x: auto;
}

.data-table {
  --el-table-border-color: #f0f0f0;
}

.num-highlight {
  font-weight: 600;
  color: #096dd9;
  font-variant-numeric: tabular-nums;
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

@media (max-width: 768px) {
  .chart-combo,
  .chart-curve {
    height: 280px;
  }
}
</style>
