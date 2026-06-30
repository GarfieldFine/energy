/** MyEMS 风格图表配置（浅色主题，与 README 截图接近） */

/**
 * 光伏相对市电往往很小，若分母用 e+s，光伏环会几乎看不见。
 * 与用水环类似：用对称「可视化」分母（非真实电量占比）：
 * - 市电：e / (e + s·K)
 * - 光伏：s / (s + e/K)
 */
const PV_DONUT_ELEC_PER_SOLAR_VIS = 55

/** 用水环图分母：m³ + 电力折算项（仅可视化，非物理换算系数） */
const WATER_DONUT_KWH_PER_M3_VIS = 2800

/**
 * @param {string} title
 * @param {number} value
 * @param {number} total
 * @param {string} color
 * @param {object} [meta]
 * @param {string} [meta.restName] 灰区在图例/悬停中的名称
 * @param {string} [meta.restSubtitle] 标题下方说明（绘出对比项含义）
 * @param {string} [meta.restHint] tooltip 补充说明
 * @param {(n:number)=>string} [meta.fmtMain]
 * @param {(n:number)=>string} [meta.fmtRest]
 */
export function miniDonutOption(title, value, total, color, meta = {}) {
  const v = Math.max(0, Number(value) || 0)
  const t = Math.max(1e-9, Number(total) || 1)
  const rest = Math.max(0, t - v)
  const {
    restName = '对比项',
    restSubtitle = '',
    restHint = '',
    fmtMain = (n) => String(n),
    fmtRest = (n) => String(n),
  } = meta

  return {
    backgroundColor: 'transparent',
    title: {
      text: title,
      subtext: restSubtitle || '',
      left: 'center',
      bottom: 0,
      textStyle: { fontSize: 12, color: 'rgba(0,0,0,0.65)', fontWeight: 500 },
      subtextStyle: { fontSize: 10, color: 'rgba(0,0,0,0.42)', lineHeight: 15 },
    },
    legend: { show: false },
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        const pct = p.percent != null ? p.percent : ''
        const isRest = p.name === restName
        const num = p.value != null ? p.value : ''
        const shown = isRest ? fmtRest(Number(num)) : fmtMain(Number(p.value))
        let block = `${p.marker}${p.name}<br/>${shown}（${pct}%）`
        if (isRest) {
          block += `<br/><span style="font-size:11px;color:#8c8c8c">${restHint || '环图分母中除主项外的部分（非缺失数据）'}</span>`
        }
        return block
      },
    },
    series: [
      {
        type: 'pie',
        radius: ['38%', '62%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, formatter: '{d}%', fontSize: 11, color: '#595959' },
        data: [
          { value: v, name: title, itemStyle: { color } },
          { value: rest, name: restName, itemStyle: { color: '#e8e8e8' } },
        ],
      },
    ],
  }
}

/**
 * 四项环形：市电/光伏/用水 分母见上（环上比例为可视化，tooltip 仍为原始累计值）；湿度为时段均值/100%。
 * @param {Record<string, number>|null|undefined} sums
 * @param {Record<string, number>|null|undefined} means 需含 relative_humidity_pct 均值（后端 period 接口）
 */
export function buildDonutRowFromSums(sums, means) {
  const e = Math.max(0, Number(sums?.electricity_kwh) || 0)
  const s = Math.max(0, Number(sums?.solar_kwh) || 0)
  const w = Math.max(0, Number(sums?.water_m3) || 0)
  const k = PV_DONUT_ELEC_PER_SOLAR_VIS
  const elecDen = e + s * k
  const pvDen = s + e / k
  const kwhSum = e + s || 1e-9

  const fmtKwh = (n) =>
    `${Number(n).toLocaleString('zh-CN', { maximumFractionDigits: 1 })} kWh`
  const fmtM3 = (n) => `${Number(n).toLocaleString('zh-CN', { maximumFractionDigits: 2 })} m³`
  const fmtPct = (n) => `${Number(n).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}%`

  const sWeighted = s * k
  const eScaled = e / k
  const wEquiv = kwhSum / WATER_DONUT_KWH_PER_M3_VIS
  const wDen = w + wEquiv

  const out = [
    miniDonutOption('市电', e, elecDen, '#1890ff', {
      restName: '光伏加权项',
      restSubtitle: `灰区：光伏×${k}（示意权重）`,
      restHint: `此项 = 光伏×${k} = ${fmtKwh(sWeighted)}，与市电同环对比用，非额外电量`,
      fmtMain: fmtKwh,
      fmtRest: fmtKwh,
    }),
    miniDonutOption('光伏', s, pvDen, '#52c41a', {
      restName: '市电折算项',
      restSubtitle: `灰区：市电÷${k}（示意权重）`,
      restHint: `此项 = 市电÷${k} = ${fmtKwh(eScaled)}，与光伏同环对比用`,
      fmtMain: fmtKwh,
      fmtRest: fmtKwh,
    }),
    miniDonutOption('用水', w, wDen, '#faad14', {
      restName: '电力折算项',
      restSubtitle: `灰区：(市电+光伏)÷${WATER_DONUT_KWH_PER_M3_VIS}`,
      restHint: `将 ${fmtKwh(kwhSum)} 折算为与 m³ 同屏量级：${fmtM3(wEquiv)}（仅环图用）`,
      fmtMain: fmtM3,
      fmtRest: fmtM3,
    }),
  ]

  const rh = Number(means?.relative_humidity_pct)
  const rhVal = Number.isFinite(rh) ? Math.min(100, Math.max(0, rh)) : 0
  const dry = Math.max(0, 100 - rhVal)
  out.push(
    miniDonutOption('平均湿度', rhVal, 100, '#722ed1', {
      restName: '干燥占比',
      restSubtitle: '灰区：100% − 平均湿度',
      restHint: `干燥部分 = 100% − ${fmtPct(rhVal)} = ${fmtPct(dry)}`,
      fmtMain: fmtPct,
      fmtRest: fmtPct,
    }),
  )
  return out
}

/**
 * 柱状 + 折线（报告期趋势）
 * @param {string[]} labels
 * @param {number[]} values
 * @param {object} [opts]
 * @param {number[]|null} [opts.compareValues] 与本期对齐后的对比序列（如上周同期）
 * @param {number|null} [opts.benchmarkY] 水平标杆（如对标样本建筑均时用电）
 * @param {string} [opts.compareLabel]
 */
export function comboBarLineOption(labels, values, opts = {}) {
  const { compareValues = null, benchmarkY = null, compareLabel = '对比期' } = opts
  const vals = (values ?? []).map((v) => (v == null ? 0 : Number(v)))
  const line = vals.map((v, i) => {
    const a = vals[i - 1] ?? v
    const b = vals[i + 1] ?? v
    return Number(((v + a + b) / 3).toFixed(4))
  })

  let lb = labels.length ? labels : ['—']
  let barData = vals.length ? vals : [0]
  let lineData = vals.length ? line : [0]
  let compareLine = null

  if (Array.isArray(compareValues) && compareValues.length > 0) {
    const n = Math.min(lb.length, compareValues.length)
    lb = lb.slice(0, n)
    barData = barData.slice(0, n)
    lineData = lineData.slice(0, n)
    compareLine = compareValues.slice(0, n).map((v) => (v == null ? 0 : Number(v)))
  }

  const legendData = ['小时值(柱)', '趋势(线)']
  if (compareLine) legendData.push(compareLabel)

  const bm =
    benchmarkY != null && Number.isFinite(Number(benchmarkY)) ? Number(benchmarkY) : null

  const series = [
    {
      name: '小时值(柱)',
      type: 'bar',
      data: barData,
      barMaxWidth: 14,
      itemStyle: { color: '#2f54eb', borderRadius: [2, 2, 0, 0] },
      markLine:
        bm != null
          ? {
              silent: true,
              symbol: 'none',
              label: { formatter: '对标样本均时', color: '#8c8c8c', fontSize: 10 },
              lineStyle: { type: 'dashed', color: '#722ed1', width: 1 },
              data: [{ yAxis: bm }],
            }
          : undefined,
    },
    {
      name: '趋势(线)',
      type: 'line',
      data: lineData,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: '#262626' },
    },
  ]

  if (compareLine) {
    series.push({
      name: compareLabel,
      type: 'line',
      data: compareLine,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: '#52c41a', type: 'dashed' },
    })
  }

  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: {
      data: legendData,
      top: 0,
      textStyle: { color: '#595959' },
    },
    grid: { left: 48, right: 24, top: compareLine ? 44 : 36, bottom: lb.length > 24 ? 48 : 32 },
    xAxis: {
      type: 'category',
      data: lb,
      axisLabel: { color: '#8c8c8c', fontSize: 10, rotate: lb.length > 20 ? 35 : 0 },
      axisLine: { lineStyle: { color: '#e8e8e8' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
      axisLabel: { color: '#8c8c8c' },
    },
    series,
  }
}

/**
 * 运行曲线：橙色折线 + 点标（点密时自动隐藏节点）
 * @param {object} [opts]
 * @param {number|null} [opts.benchmarkY] 水平标杆线（与 combo 同源时可对齐）
 */
export function operationCurveOption(labels, values, opts = {}) {
  const { benchmarkY = null } = opts
  const n = values?.length ?? 0
  const vals = (values ?? []).map((v) => (v == null ? 0 : Number(v)))
  const bm =
    benchmarkY != null && Number.isFinite(Number(benchmarkY)) ? Number(benchmarkY) : null
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, top: 28, bottom: labels.length > 24 ? 44 : 28 },
    xAxis: {
      type: 'category',
      data: labels.length ? labels : ['—'],
      axisLabel: { color: '#8c8c8c', fontSize: 10, rotate: labels.length > 20 ? 35 : 0 },
      axisLine: { lineStyle: { color: '#e8e8e8' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f0f0', type: 'dashed' } },
      axisLabel: { color: '#8c8c8c' },
    },
    series: [
      {
        type: 'line',
        data: vals.length ? vals : [0],
        smooth: true,
        lineStyle: { width: 2, color: '#fa8c16' },
        itemStyle: { color: '#fa8c16' },
        showSymbol: n > 0 && n <= 64,
        symbolSize: 7,
        markLine:
          bm != null
            ? {
                silent: true,
                symbol: 'none',
                label: { formatter: '对标样本均时', color: '#8c8c8c', fontSize: 10 },
                lineStyle: { type: 'dashed', color: '#722ed1', width: 1 },
                data: [{ yAxis: bm }],
              }
            : undefined,
      },
    ],
  }
}
