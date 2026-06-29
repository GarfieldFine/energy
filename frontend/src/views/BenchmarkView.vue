<script setup>
import { computed, onMounted, ref } from 'vue'
import AppChart from '@/components/AppChart.vue'
import EmsDrawer from '@/components/EmsDrawer.vue'
import * as api from '@/api'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'

const formulaDialogVisible = ref(false)

const timeFrom = ref('')
const timeTo = ref('')
const topN = ref(20)
const data = ref(null)
const loading = ref(false)

const tableRows = computed(() => data.value?.items ?? [])

const SCORE_WEIGHTS = {
  total_electricity_kwh: 0.45,
  night_base_ratio: 0.35,
  peak_valley_ratio: 0.2,
}

const displayWeights = computed(() => data.value?.weights ?? SCORE_WEIGHTS)

const barOption = computed(() => {
  const labels = data.value?.chart?.labels ?? []
  const scores = data.value?.chart?.scores ?? []
  return {
    color: ['#1890ff'],
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, top: 40, bottom: 56 },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 35, fontSize: 11 } },
    yAxis: { type: 'value', name: '综合分', max: 100, splitLine: { lineStyle: { type: 'dashed' } } },
    series: [
      {
        type: 'bar',
        data: scores,
        barMaxWidth: 36,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
})

async function load() {
  loading.value = true
  try {
    const params = { top_n: topN.value }
    if (timeFrom.value) params.time_from = timeFrom.value
    if (timeTo.value) params.time_to = timeTo.value
    data.value = await api.getBenchmarkScoreboard(params)
  } catch (e) {
    ElMessage.error(e.message ?? '加载失败')
    data.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-head page-head--end">
      <el-button :icon="InfoFilled" @click="formulaDialogVisible = true">
        综合分计算权重
      </el-button>
    </div>

    <EmsDrawer v-model="formulaDialogVisible" title="综合分计算权重" size="520px">
      <code class="formula-expr">
        Score = 100 × ({{ displayWeights.total_electricity_kwh }} × norm(总电耗) + {{
          displayWeights.night_base_ratio
        }} × norm(夜间基荷占比) + {{ displayWeights.peak_valley_ratio }} × norm(峰谷比))
      </code>
      <ul class="formula-detail">
        <li>
          <strong>norm(指标)</strong>：时段内各建筑横向归一化，指标越低越优时
          <code>norm = (max − x) / (max − min)</code>；若 max = min 则取 1.0
        </li>
        <li>
          <strong>总电耗</strong>：筛选时段内 <code>electricity_kwh</code> 求和（kWh）
        </li>
        <li>
          <strong>夜间基荷占比</strong>：0–5 时电耗之和 ÷ 总电耗
        </li>
        <li>
          <strong>峰谷比</strong>：小时电耗 P95 ÷ P05
        </li>
        <li>综合分越高表示相对能效越好；排行榜按 Score 降序取 Top N</li>
      </ul>
      <div class="weight-tags">
        <el-tag type="info" effect="plain" size="small">
          总电耗权重 {{ (displayWeights.total_electricity_kwh * 100).toFixed(0) }}%
        </el-tag>
        <el-tag type="info" effect="plain" size="small">
          夜间基荷权重 {{ (displayWeights.night_base_ratio * 100).toFixed(0) }}%
        </el-tag>
        <el-tag type="info" effect="plain" size="small">
          峰谷比权重 {{ (displayWeights.peak_valley_ratio * 100).toFixed(0) }}%
        </el-tag>
      </div>
      <template #footer>
        <el-button type="primary" round @click="formulaDialogVisible = false">知道了</el-button>
      </template>
    </EmsDrawer>

    <el-card shadow="never" class="ems-card filter-card">
      <el-form :inline="true">
        <el-form-item label="开始时间">
          <el-input v-model="timeFrom" placeholder="YYYY-MM-DD HH:MM:SS" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-input v-model="timeTo" placeholder="YYYY-MM-DD HH:MM:SS" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="上榜数量">
          <el-input-number v-model="topN" :min="3" :max="200" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="mt">
      <el-col :xs="24" :lg="14">
        <el-card v-loading="loading" shadow="never" class="ems-card">
          <template #header>排行榜</template>
          <el-table v-if="tableRows.length" :data="tableRows" stripe border max-height="520" size="small">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="rank" label="名次" width="72" />
            <el-table-column prop="building_id" label="建筑" min-width="160" show-overflow-tooltip />
            <el-table-column prop="score" label="综合分" width="88" sortable />
            <el-table-column prop="total_electricity_kwh" label="总电耗" min-width="110" show-overflow-tooltip />
            <el-table-column prop="night_base_ratio" label="夜间基荷占比" min-width="120" />
            <el-table-column prop="peak_valley_ratio" label="峰谷比" min-width="100" />
          </el-table>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card v-loading="loading" shadow="never" class="ems-card chart-card">
          <template #header>得分分布（柱状）</template>
          <AppChart v-if="data?.chart?.labels?.length" :option="barOption" />
          <el-empty v-else description="暂无图表数据" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
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

.filter-card {
  margin-bottom: 0;
}

.mt {
  margin-top: 16px;
}

.chart-card {
  min-height: 400px;
}
</style>
