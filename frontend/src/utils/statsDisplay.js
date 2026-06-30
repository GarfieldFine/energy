/** 统计分析页：字段展示名、单位、合计列是否展示（均值类指标合计无业务含义时可隐藏） */

export const STATS_FIELD_ORDER = [
  'electricity_kwh',
  'solar_kwh',
  'chilledwater_kwh_eq',
  'hotwater_kwh',
  'water_m3',
  'air_temperature_c',
  'relative_humidity_pct',
]

export const STATS_FIELD_META = {
  electricity_kwh: { label: '市电用电', unit: 'kWh', showSum: true },
  solar_kwh: { label: '光伏发电', unit: 'kWh', showSum: true },
  chilledwater_kwh_eq: { label: '冷量当量', unit: 'kWh', showSum: true },
  hotwater_kwh: { label: '热水能耗', unit: 'kWh', showSum: true },
  water_m3: { label: '用水量', unit: 'm³', showSum: true },
  air_temperature_c: { label: '空气温度', unit: '℃', showSum: false },
  relative_humidity_pct: { label: '相对湿度', unit: '%RH', showSum: false },
}

export function formatStatValue(key, value, role) {
  if (value == null || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  const meta = STATS_FIELD_META[key]
  if (role === 'sum' && meta && !meta.showSum) return '—'
  if (key === 'water_m3') return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 3 })
  if (key === 'relative_humidity_pct' || key === 'air_temperature_c')
    return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
  if (role === 'mean' && (key === 'relative_humidity_pct' || key === 'air_temperature_c'))
    return n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

/**
 * @param {Record<string, number|null|undefined>|null|undefined} sums
 * @param {Record<string, number|null|undefined>|null|undefined} means
 */
/** ISO 时间串缩略展示 */
export function formatIsoRange(min, max) {
  if (!min || !max) return '—'
  const a = String(min).replace('T', ' ').slice(0, 19)
  const b = String(max).replace('T', ' ').slice(0, 19)
  return `${a} — ${b}`
}

export function buildPeriodTableRows(sums, means) {
  if (!sums || typeof sums !== 'object') return []
  const keys = [
    ...STATS_FIELD_ORDER.filter((k) => k in sums),
    ...Object.keys(sums).filter((k) => !STATS_FIELD_ORDER.includes(k)),
  ]
  return keys.map((key) => {
    const meta = STATS_FIELD_META[key] ?? { label: key, unit: '', showSum: true }
    return {
      key,
      label: meta.label,
      unit: meta.unit,
      showSum: meta.showSum !== false,
      sumFmt: formatStatValue(key, sums[key], 'sum'),
      meanFmt: formatStatValue(key, means?.[key], 'mean'),
    }
  })
}
