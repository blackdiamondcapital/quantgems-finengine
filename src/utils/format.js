export function formatMoney(value, { isEps = false } = {}) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const n = Number(value)
  if (isEps) {
    return n.toLocaleString('zh-TW', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  }
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(2)} 兆`
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(2)} 億`
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(2)} 萬`
  return `${sign}${abs.toLocaleString('zh-TW', { maximumFractionDigits: 0 })}`
}

export function formatPct(value, digits = 1) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const n = Number(value)
  return `${(n * 100).toFixed(digits)}%`
}

const MULTIPLE_RATIO_KEYS = new Set([
  'current_ratio',
  'quick_ratio',
  'cash_ratio',
  'cash_cl_ratio',
  'debt_to_equity',
  'operating_cash_to_net_income',
  'interest_coverage',
  'asset_turnover',
  'inventory_turnover',
  'receivable_turnover',
  'payable_turnover',
  'dupont_asset_turnover',
  'dupont_equity_multiplier',
])

const DAY_RATIO_KEYS = new Set([
  'inventory_days',
  'receivable_days',
  'payable_days',
  'cash_conversion_cycle',
])

const CURRENCY_RATIO_KEYS = new Set([
  'operating_cash_flow',
  'free_cash_flow',
  'book_value_per_share',
  'free_cash_flow_per_share',
])

export function ratioUnit(key) {
  if (MULTIPLE_RATIO_KEYS.has(key)) return 'multiple'
  if (DAY_RATIO_KEYS.has(key)) return 'days'
  if (CURRENCY_RATIO_KEYS.has(key)) return 'currency'
  return 'percent'
}

export function formatByUnit(value, unit, { key = '', applicable = true } = {}) {
  if (value == null || Number.isNaN(Number(value))) {
    return applicable === false ? '不適用' : '—'
  }
  const n = Number(value)
  if (unit === 'multiple') return `${n.toFixed(2)} 倍`
  if (unit === 'days') return `${n.toFixed(1)} 天`
  if (unit === 'currency') {
    const isPerShare = key === 'book_value_per_share' || key === 'free_cash_flow_per_share'
    return `${formatMoney(n, { isEps: isPerShare })} 元`
  }
  return formatPct(n)
}

export function formatRatio(key, value, unit = ratioUnit(key), options = {}) {
  return formatByUnit(value, unit, { key, ...options })
}

export function changeClass(curr, prev) {
  if (curr == null || prev == null) return ''
  if (curr > prev) return 'up'
  if (curr < prev) return 'down'
  return ''
}

export function changePct(curr, prev) {
  if (curr == null || prev == null || prev === 0) return null
  return ((curr - prev) / Math.abs(prev)) * 100
}
