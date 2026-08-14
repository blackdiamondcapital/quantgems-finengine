<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import { formatMoney, formatRatio } from '../utils/format'
import AuthBar from './AuthBar.vue'
import { MAIN_SITE_URL, PRICING_URL } from '../lib/siteLinks'
import { useAuth } from '../lib/auth'
import { buildOAuthStartUrl } from '../lib/oauthStart'
import {
  canUseScreener,
  SCREENER_LOGIN_REQUIRED_MESSAGE,
  SCREENER_PLAN_REQUIRED_MESSAGE,
} from '../utils/planAccess'

const emit = defineEmits(['open-stock', 'goto-engine', 'back'])

const { user, isAuthenticated } = useAuth()
const allowed = computed(() => canUseScreener(user.value))
const gateKind = computed(() => {
  if (allowed.value) return null
  if (!isAuthenticated.value || !user.value) return 'login'
  return 'plan'
})
const gateMessage = computed(() => (
  gateKind.value === 'login'
    ? SCREENER_LOGIN_REQUIRED_MESSAGE
    : SCREENER_PLAN_REQUIRED_MESSAGE
))

const loading = ref(false)
const exporting = ref(false)
const error = ref('')
const meta = ref(null)
const result = ref(null)
const resultKeyword = ref('')
const syncingUrl = ref(false)

const ADVANCED_FILTER_GROUPS = [
  {
    id: 'cashflow',
    title: '現金流品質',
    fields: [
      { key: 'operating_cash_to_net_income_min', label: '營業現金流／淨利 ≥', unit: 'multiple', placeholder: '例 1' },
      { key: 'free_cash_flow_margin_min', label: '自由現金流率 ≥ %', unit: 'percent', placeholder: '例 5' },
      { key: 'roic_min', label: 'ROIC ≥ %', unit: 'percent', placeholder: '例 12' },
      { key: 'interest_coverage_min', label: '利息保障倍數 ≥', unit: 'multiple', placeholder: '例 5' },
    ],
  },
  {
    id: 'efficiency',
    title: '營運效率',
    fields: [
      { key: 'asset_turnover_min', label: '資產週轉率 ≥', unit: 'multiple', placeholder: '例 0.8' },
      { key: 'inventory_turnover_min', label: '存貨週轉率 ≥', unit: 'multiple', placeholder: '例 4' },
      { key: 'receivable_turnover_min', label: '應收週轉率 ≥', unit: 'multiple', placeholder: '例 6' },
      { key: 'cash_conversion_cycle_max', label: '現金轉換週期 ≤ 天', unit: 'days', placeholder: '例 120' },
    ],
  },
  {
    id: 'growth',
    title: '成長性',
    fields: [
      { key: 'revenue_yoy_min', label: '營收年增率 ≥ %', unit: 'percent', placeholder: '例 10' },
      { key: 'op_profit_yoy_min', label: '營業利益年增率 ≥ %', unit: 'percent', placeholder: '例 10' },
      { key: 'eps_yoy_min', label: 'EPS 年增率 ≥ %', unit: 'percent', placeholder: '例 10' },
      { key: 'revenue_cagr_3y_min', label: '營收 CAGR 3Y ≥ %', unit: 'percent', placeholder: '例 8' },
      { key: 'eps_cagr_3y_min', label: 'EPS CAGR 3Y ≥ %', unit: 'percent', placeholder: '例 8' },
    ],
  },
  {
    id: 'per-share-dupont',
    title: '每股指標／杜邦分析',
    fields: [
      { key: 'book_value_per_share_min', label: '每股淨值 ≥ 元', unit: 'currency', placeholder: '例 20' },
      { key: 'free_cash_flow_per_share_min', label: '每股自由現金流 ≥ 元', unit: 'currency', placeholder: '例 2' },
      { key: 'dupont_net_margin_min', label: '杜邦淨利率 ≥ %', unit: 'percent', placeholder: '例 10' },
      { key: 'dupont_equity_multiplier_max', label: '杜邦權益乘數 ≤', unit: 'multiple', placeholder: '例 3' },
    ],
  },
]

const ADVANCED_FILTER_FIELDS = ADVANCED_FILTER_GROUPS.flatMap((group) => group.fields)
const ADVANCED_FILTER_KEYS = ADVANCED_FILTER_FIELDS.map((field) => field.key)
const ADVANCED_RESULT_COLUMNS = [
  ['operating_cash_flow', '營業現金流', 'currency'],
  ['free_cash_flow', '自由現金流', 'currency'],
  ['operating_cash_to_net_income', '現金流／淨利', 'multiple'],
  ['free_cash_flow_margin', '自由現金流率', 'percent'],
  ['roic', 'ROIC', 'percent'],
  ['interest_coverage', '利息保障倍數', 'multiple'],
  ['asset_turnover', '資產週轉率', 'multiple'],
  ['inventory_turnover', '存貨週轉率', 'multiple'],
  ['receivable_turnover', '應收週轉率', 'multiple'],
  ['payable_turnover', '應付週轉率', 'multiple'],
  ['inventory_days', '存貨天數', 'days'],
  ['receivable_days', '應收天數', 'days'],
  ['payable_days', '應付天數', 'days'],
  ['cash_conversion_cycle', '現金轉換週期', 'days'],
  ['revenue_yoy', '營收年增率', 'percent'],
  ['op_profit_yoy', '營業利益年增率', 'percent'],
  ['eps_yoy', 'EPS 年增率', 'percent'],
  ['revenue_cagr_3y', '營收 CAGR 3Y', 'percent'],
  ['eps_cagr_3y', 'EPS CAGR 3Y', 'percent'],
  ['book_value_per_share', '每股淨值', 'currency'],
  ['free_cash_flow_per_share', '每股自由現金流', 'currency'],
  ['dupont_net_margin', '杜邦淨利率', 'percent'],
  ['dupont_asset_turnover', '杜邦資產週轉率', 'multiple'],
  ['dupont_equity_multiplier', '杜邦權益乘數', 'multiple'],
].map(([key, label, unit]) => ({ key, label, unit }))

const form = reactive({
  preset: 'high_roe',
  market: 'both',
  industry: '',
  period: 'latest',
  roe_min: '',
  roa_min: '',
  gross_margin_min: '',
  op_margin_min: '',
  net_margin_min: '',
  debt_ratio_max: '',
  current_ratio_min: '',
  quick_ratio_min: '',
  revenue_min: '',
  pe_max: '',
  pb_max: '',
  dy_min: '',
  roe_min_streak: false,
  sort: 'roe',
  dir: 'desc',
  page: 1,
  ...Object.fromEntries(ADVANCED_FILTER_KEYS.map((key) => [key, ''])),
})

const presets = computed(() => meta.value?.presets || result.value?.presets || [])
const industries = computed(() => meta.value?.industries || [])
const periods = computed(() => meta.value?.periods || [])
const items = computed(() => result.value?.items || [])
const total = computed(() => result.value?.total || 0)
const pageSize = computed(() => result.value?.pageSize || 50)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const resultColumnCount = 14 + ADVANCED_RESULT_COLUMNS.length

const filteredItems = computed(() => {
  const q = resultKeyword.value.trim().toLowerCase()
  if (!q) return items.value
  return items.value.filter((row) => {
    const code = String(row.code || '').toLowerCase()
    const name = String(row.name || '').toLowerCase()
    return code.includes(q) || name.includes(q)
  })
})

function pctInputToRatio(v) {
  if (v === '' || v == null) return undefined
  const n = Number(v)
  if (Number.isNaN(n)) return undefined
  return n / 100
}

function ratioToPctInput(v) {
  if (v == null || v === '') return ''
  const n = Number(v)
  if (Number.isNaN(n)) return ''
  return String(Number((n * 100).toFixed(4)))
}

function buildQuery({ page, pageSize: size } = {}) {
  const q = {
    market: form.market,
    industry: form.industry || undefined,
    period: form.period || 'latest',
    sort: form.sort,
    dir: form.dir,
    page: page ?? form.page,
    page_size: size ?? 50,
  }

  if (form.preset) q.preset = form.preset

  const roeMin = pctInputToRatio(form.roe_min)
  const roaMin = pctInputToRatio(form.roa_min)
  const gmMin = pctInputToRatio(form.gross_margin_min)
  const opMin = pctInputToRatio(form.op_margin_min)
  const netMin = pctInputToRatio(form.net_margin_min)
  const debtMax = pctInputToRatio(form.debt_ratio_max)
  if (roeMin != null) q.roe_min = roeMin
  if (roaMin != null) q.roa_min = roaMin
  if (gmMin != null) q.gross_margin_min = gmMin
  if (opMin != null) q.op_margin_min = opMin
  if (netMin != null) q.net_margin_min = netMin
  if (debtMax != null) q.debt_ratio_max = debtMax
  if (form.current_ratio_min !== '') q.current_ratio_min = Number(form.current_ratio_min)
  if (form.quick_ratio_min !== '') q.quick_ratio_min = Number(form.quick_ratio_min)
  if (form.revenue_min !== '') q.revenue_min = Number(form.revenue_min)
  if (form.pe_max !== '') q.pe_max = Number(form.pe_max)
  if (form.pb_max !== '') q.pb_max = Number(form.pb_max)
  if (form.dy_min !== '') q.dy_min = Number(form.dy_min)
  if (form.roe_min_streak) q.roe_min_streak = 2
  for (const field of ADVANCED_FILTER_FIELDS) {
    if (form[field.key] === '') continue
    const value = field.unit === 'percent'
      ? pctInputToRatio(form[field.key])
      : Number(form[field.key])
    if (value != null && !Number.isNaN(value)) q[field.key] = value
  }

  return q
}

function clearManualThresholds() {
  form.roe_min = ''
  form.roa_min = ''
  form.gross_margin_min = ''
  form.op_margin_min = ''
  form.net_margin_min = ''
  form.debt_ratio_max = ''
  form.current_ratio_min = ''
  form.quick_ratio_min = ''
  form.revenue_min = ''
  form.pe_max = ''
  form.pb_max = ''
  form.dy_min = ''
  form.roe_min_streak = false
  for (const key of ADVANCED_FILTER_KEYS) form[key] = ''
}

function fillFormFromFilters(filters = {}) {
  clearManualThresholds()
  if (filters.roe_min != null) form.roe_min = ratioToPctInput(filters.roe_min)
  if (filters.roa_min != null) form.roa_min = ratioToPctInput(filters.roa_min)
  if (filters.gross_margin_min != null) form.gross_margin_min = ratioToPctInput(filters.gross_margin_min)
  if (filters.op_margin_min != null) form.op_margin_min = ratioToPctInput(filters.op_margin_min)
  if (filters.net_margin_min != null) form.net_margin_min = ratioToPctInput(filters.net_margin_min)
  if (filters.debt_ratio_max != null) form.debt_ratio_max = ratioToPctInput(filters.debt_ratio_max)
  if (filters.current_ratio_min != null) form.current_ratio_min = String(filters.current_ratio_min)
  if (filters.quick_ratio_min != null) form.quick_ratio_min = String(filters.quick_ratio_min)
  if (filters.revenue_min != null) form.revenue_min = String(filters.revenue_min)
  if (filters.pe_max != null) form.pe_max = String(filters.pe_max)
  if (filters.pb_max != null) form.pb_max = String(filters.pb_max)
  if (filters.dy_min != null) form.dy_min = String(filters.dy_min)
  form.roe_min_streak = Number(filters.roe_min_streak || 0) >= 2
  for (const field of ADVANCED_FILTER_FIELDS) {
    const value = filters[field.key]
    if (value == null) continue
    form[field.key] = field.unit === 'percent' ? ratioToPctInput(value) : String(value)
  }
}

async function loadMeta() {
  if (!allowed.value) return
  try {
    meta.value = await api.screenerMeta()
  } catch {
    meta.value = null
  }
}

function writeUrlState() {
  if (syncingUrl.value) return
  try {
    const params = new URLSearchParams()
    params.set('view', 'screener')
    if (form.preset) params.set('preset', form.preset)
    if (form.market && form.market !== 'both') params.set('market', form.market)
    if (form.industry) params.set('industry', form.industry)
    if (form.period && form.period !== 'latest') params.set('period', form.period)
    if (form.roe_min !== '') params.set('roe_min', form.roe_min)
    if (form.roa_min !== '') params.set('roa_min', form.roa_min)
    if (form.gross_margin_min !== '') params.set('gross_margin_min', form.gross_margin_min)
    if (form.op_margin_min !== '') params.set('op_margin_min', form.op_margin_min)
    if (form.net_margin_min !== '') params.set('net_margin_min', form.net_margin_min)
    if (form.debt_ratio_max !== '') params.set('debt_ratio_max', form.debt_ratio_max)
    if (form.current_ratio_min !== '') params.set('current_ratio_min', form.current_ratio_min)
    if (form.quick_ratio_min !== '') params.set('quick_ratio_min', form.quick_ratio_min)
    if (form.revenue_min !== '') params.set('revenue_min', form.revenue_min)
    if (form.pe_max !== '') params.set('pe_max', form.pe_max)
    if (form.pb_max !== '') params.set('pb_max', form.pb_max)
    if (form.dy_min !== '') params.set('dy_min', form.dy_min)
    if (form.roe_min_streak) params.set('roe_min_streak', '2')
    for (const key of ADVANCED_FILTER_KEYS) {
      if (form[key] !== '') params.set(key, form[key])
    }
    if (form.sort && form.sort !== 'roe') params.set('sort', form.sort)
    if (form.dir && form.dir !== 'desc') params.set('dir', form.dir)
    if (form.page > 1) params.set('page', String(form.page))
    if (resultKeyword.value.trim()) params.set('kq', resultKeyword.value.trim())
    const qs = params.toString()
    const next = `${window.location.pathname}${qs ? `?${qs}` : ''}${window.location.hash || ''}`
    window.history.replaceState(null, '', next)
  } catch {
    /* ignore */
  }
}

function readUrlState() {
  try {
    const params = new URLSearchParams(window.location.search)
    if ((params.get('view') || '') !== 'screener' && !params.get('preset') && !params.get('roe_min')) {
      return false
    }
    syncingUrl.value = true
    if (params.has('preset')) form.preset = params.get('preset') || ''
    if (params.has('market')) form.market = params.get('market') || 'both'
    if (params.has('industry')) form.industry = params.get('industry') || ''
    if (params.has('period')) form.period = params.get('period') || 'latest'
    if (params.has('roe_min')) form.roe_min = params.get('roe_min') || ''
    if (params.has('roa_min')) form.roa_min = params.get('roa_min') || ''
    if (params.has('gross_margin_min')) form.gross_margin_min = params.get('gross_margin_min') || ''
    if (params.has('op_margin_min')) form.op_margin_min = params.get('op_margin_min') || ''
    if (params.has('net_margin_min')) form.net_margin_min = params.get('net_margin_min') || ''
    if (params.has('debt_ratio_max')) form.debt_ratio_max = params.get('debt_ratio_max') || ''
    if (params.has('current_ratio_min')) form.current_ratio_min = params.get('current_ratio_min') || ''
    if (params.has('quick_ratio_min')) form.quick_ratio_min = params.get('quick_ratio_min') || ''
    if (params.has('revenue_min')) form.revenue_min = params.get('revenue_min') || ''
    if (params.has('pe_max')) form.pe_max = params.get('pe_max') || ''
    if (params.has('pb_max')) form.pb_max = params.get('pb_max') || ''
    if (params.has('dy_min')) form.dy_min = params.get('dy_min') || ''
    for (const key of ADVANCED_FILTER_KEYS) {
      if (params.has(key)) form[key] = params.get(key) || ''
    }
    form.roe_min_streak = params.get('roe_min_streak') === '2' || params.get('roe_min_streak') === '1'
    if (params.has('sort')) form.sort = params.get('sort') || 'roe'
    if (params.has('dir')) form.dir = params.get('dir') || 'desc'
    if (params.has('page')) form.page = Math.max(1, Number(params.get('page')) || 1)
    if (params.has('kq')) resultKeyword.value = params.get('kq') || ''
    syncingUrl.value = false
    return true
  } catch {
    syncingUrl.value = false
    return false
  }
}

async function runScreen() {
  if (!allowed.value) {
    result.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    result.value = await api.screener(buildQuery())
    writeUrlState()
  } catch (e) {
    error.value = e?.message || '選股失敗'
    result.value = null
  } finally {
    loading.value = false
  }
}

function startGoogleLogin() {
  window.location.href = buildOAuthStartUrl('google')
}

function applyPreset(id) {
  const next = form.preset === id ? '' : id
  form.preset = next
  form.page = 1
  if (next) {
    const p = presets.value.find((x) => x.id === next)
    fillFormFromFilters(p?.filters || {})
  } else {
    clearManualThresholds()
  }
  runScreen()
}

function submitFilters() {
  form.page = 1
  runScreen()
}

function clearFilters() {
  form.preset = ''
  form.market = 'both'
  form.industry = ''
  form.period = 'latest'
  clearManualThresholds()
  form.sort = 'roe'
  form.dir = 'desc'
  form.page = 1
  resultKeyword.value = ''
  runScreen()
}

function toggleSort(key) {
  if (form.sort === key) {
    form.dir = form.dir === 'desc' ? 'asc' : 'desc'
  } else {
    form.sort = key
    form.dir = ['debt_ratio', 'pe', 'pb'].includes(key) ? 'asc' : 'desc'
  }
  form.page = 1
  runScreen()
}

function sortMark(key) {
  if (form.sort !== key) return ''
  return form.dir === 'asc' ? ' ↑' : ' ↓'
}

function goPage(delta) {
  const next = form.page + delta
  if (next < 1 || next > totalPages.value) return
  form.page = next
  runScreen()
}

function openStock(row) {
  emit('open-stock', row.code)
}

function marketLabel(m) {
  if (m === 'listed') return '上市'
  if (m === 'otc') return '上櫃'
  return m || '—'
}

function formatResultValue(row, column) {
  return formatRatio(column.key, row[column.key], column.unit)
}

function htmlEscape(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

async function exportExcel() {
  if (!allowed.value || exporting.value) return
  exporting.value = true
  error.value = ''
  try {
    const rows = []
    const maxRows = 2000
    const size = 100
    let page = 1
    let fetched = 0
    let totalCount = Infinity
    while (fetched < totalCount && fetched < maxRows) {
      const data = await api.screener(buildQuery({ page, pageSize: size }))
      totalCount = Number(data.total) || 0
      const batch = data.items || []
      if (!batch.length) break
      for (const row of batch) {
        rows.push(row)
        fetched += 1
        if (fetched >= maxRows) break
      }
      if (batch.length < size) break
      page += 1
    }
    const baseColumns = [
      ['code', '代號'], ['name', '名稱'], ['market', '市場'], ['industry', '產業'],
      ['roe', 'ROE'], ['roa', 'ROA'], ['gross_margin', '毛利率'], ['op_margin', '營業利益率'],
      ['net_margin', '淨利率'], ['debt_ratio', '負債比'], ['current_ratio', '流動比'],
      ['quick_ratio', '速動比'], ['revenue', '營收'], ['pe', '本益比'],
      ['pb', '股價淨值比'], ['dy', '殖利率'],
    ].map(([key, label]) => ({ key, label }))
    const columns = [...baseColumns, ...ADVANCED_RESULT_COLUMNS]
    const header = columns.map((column) => `<th>${htmlEscape(column.label)}</th>`).join('')
    const body = rows.map((row) => {
      const cells = columns.map((column) => {
        let value = row[column.key]
        if (column.key === 'market') value = marketLabel(value)
        if (column.unit) value = formatResultValue(row, column)
        return `<td>${htmlEscape(value ?? '')}</td>`
      }).join('')
      return `<tr>${cells}</tr>`
    }).join('')
    const workbook = `\uFEFF<html><head><meta charset="utf-8"></head><body><table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></body></html>`
    const blob = new Blob([workbook], { type: 'application/vnd.ms-excel;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `財務選股_${result.value?.period || 'latest'}.xls`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e?.message || '匯出失敗'
  } finally {
    exporting.value = false
  }
}

watch(
  () => form.market,
  () => {
    form.page = 1
  },
)

watch(resultKeyword, () => {
  writeUrlState()
})

watch(allowed, async (ok) => {
  if (!ok) {
    result.value = null
    meta.value = null
    return
  }
  await loadMeta()
  await runScreen()
})

onMounted(async () => {
  readUrlState()
  if (!allowed.value) return
  await loadMeta()
  if (form.preset && !form.roe_min && !form.debt_ratio_max && !form.roe_min_streak) {
    const p = presets.value.find((x) => x.id === form.preset)
    if (p?.filters) fillFormFromFilters(p.filters)
  }
  await runScreen()
})
</script>

<template>
  <section class="screener">
    <header class="bar">
      <div class="bar-nav">
        <a class="home-link" :href="MAIN_SITE_URL" target="_blank" rel="noopener noreferrer">
          <span class="home-link__full">QuantGems® 主站</span>
          <span class="home-link__short">主站</span>
        </a>
        <span class="nav-sep" aria-hidden="true">·</span>
        <button class="nav-back" type="button" @click="$emit('goto-engine')">← 財報工作台</button>
      </div>
      <div class="brand-line">
        <img
          class="brand-icon"
          src="/quantgems-finengine-icon.png"
          alt="QuantGems 財報引擎"
          width="30"
          height="30"
          decoding="async"
        />
        <span class="brand-title">
          <span class="brand-title__name">QuantGems®</span>
          <span class="brand-title__tag">選股</span>
        </span>
      </div>
      <div class="spacer" />
      <div class="bar-actions">
        <button class="ghost btn-engine" type="button" @click="$emit('goto-engine')">
          <span class="btn-engine__full">財報工作台</span>
          <span class="btn-engine__short">財報</span>
        </button>
        <AuthBar />
      </div>
    </header>

    <div class="intro">
      <h1 class="display">財務選股</h1>
      <p class="muted">
        以季報財務比率篩選台股；點選股票可進入財報引擎查看完整報表。
        <span v-if="result?.periodLabel">資料期別 {{ result.periodLabel }}</span>
      </p>
      <p class="pro-badge muted">Pro 方案功能</p>
    </div>

    <div v-if="!allowed" class="pro-gate anim-rise">
      <p class="pro-gate__eyebrow">QuantGems® Pro</p>
      <h2 class="pro-gate__title">財務選股需 Pro 方案</h2>
      <p class="pro-gate__msg muted">{{ gateMessage }}</p>
      <div class="pro-gate__actions">
        <button
          v-if="gateKind === 'login'"
          type="button"
          class="cta"
          @click="startGoogleLogin"
        >
          Google 登入
        </button>
        <a
          class="cta pro-gate__link"
          :href="PRICING_URL"
          target="_blank"
          rel="noopener noreferrer"
        >
          前往方案頁
        </a>
        <button type="button" class="ghost" @click="$emit('goto-engine')">返回財報工作台</button>
      </div>
    </div>

    <template v-else>
    <div class="presets">
      <button
        v-for="p in presets"
        :key="p.id"
        type="button"
        class="preset"
        :class="{ active: form.preset === p.id }"
        @click="applyPreset(p.id)"
      >
        <span class="preset-label">{{ p.label }}</span>
        <span class="preset-desc muted">{{ p.desc }}</span>
      </button>
    </div>

    <form class="filters" @submit.prevent="submitFilters">
      <label>
        <span>市場</span>
        <select v-model="form.market">
          <option value="both">上市＋上櫃</option>
          <option value="listed">上市</option>
          <option value="otc">上櫃</option>
        </select>
      </label>
      <label>
        <span>產業</span>
        <select v-model="form.industry">
          <option value="">全部產業</option>
          <option v-for="ind in industries" :key="ind" :value="ind">{{ ind }}</option>
        </select>
      </label>
      <label>
        <span>期別</span>
        <select v-model="form.period">
          <option value="latest">最新一期</option>
          <option v-for="p in periods" :key="p.value" :value="p.value">{{ p.label }}</option>
        </select>
      </label>
      <label>
        <span>ROE ≥ %</span>
        <input v-model="form.roe_min" type="number" step="0.1" placeholder="例 15" />
      </label>
      <label>
        <span>ROA ≥ %</span>
        <input v-model="form.roa_min" type="number" step="0.1" placeholder="例 8" />
      </label>
      <label>
        <span>毛利率 ≥ %</span>
        <input v-model="form.gross_margin_min" type="number" step="0.1" placeholder="例 30" />
      </label>
      <label>
        <span>營業利益率 ≥ %</span>
        <input v-model="form.op_margin_min" type="number" step="0.1" placeholder="例 10" />
      </label>
      <label>
        <span>淨利率 ≥ %</span>
        <input v-model="form.net_margin_min" type="number" step="0.1" placeholder="例 8" />
      </label>
      <label>
        <span>負債比 ≤ %</span>
        <input v-model="form.debt_ratio_max" type="number" step="0.1" placeholder="例 50" />
      </label>
      <label>
        <span>流動比 ≥</span>
        <input v-model="form.current_ratio_min" type="number" step="0.1" placeholder="例 1.2" />
      </label>
      <label>
        <span>速動比 ≥</span>
        <input v-model="form.quick_ratio_min" type="number" step="0.1" placeholder="例 1" />
      </label>
      <label>
        <span>營收 ≥（報表單位）</span>
        <input v-model="form.revenue_min" type="number" step="1" placeholder="例 1000000" />
      </label>
      <label>
        <span>本益比 ≤</span>
        <input v-model="form.pe_max" type="number" step="0.1" placeholder="例 15" />
      </label>
      <label>
        <span>股價淨值比 ≤</span>
        <input v-model="form.pb_max" type="number" step="0.1" placeholder="例 2" />
      </label>
      <label>
        <span>殖利率 ≥ %</span>
        <input v-model="form.dy_min" type="number" step="0.1" placeholder="例 3" />
      </label>
      <label class="check-label">
        <span>連續兩季 ROE</span>
        <span class="check-row">
          <input v-model="form.roe_min_streak" type="checkbox" />
          <span class="check-hint">當季＋上一季皆達 ROE 門檻</span>
        </span>
      </label>
      <fieldset
        v-for="group in ADVANCED_FILTER_GROUPS"
        :key="group.id"
        class="filter-group"
      >
        <legend>{{ group.title }}</legend>
        <label v-for="field in group.fields" :key="field.key">
          <span>{{ field.label }}</span>
          <input
            v-model="form[field.key]"
            type="number"
            step="0.01"
            :placeholder="field.placeholder"
          />
        </label>
      </fieldset>
      <div class="filter-actions">
        <button class="cta" type="submit" :disabled="loading">套用條件</button>
        <button class="ghost" type="button" :disabled="loading" @click="clearFilters">清除</button>
      </div>
    </form>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="result-bar muted">
      <span v-if="loading">篩選中…</span>
      <span v-else>
        符合 {{ total.toLocaleString('zh-TW') }} 檔
        <template v-if="resultKeyword.trim()">
          · 本頁顯示 {{ filteredItems.length.toLocaleString('zh-TW') }} 檔
        </template>
      </span>
      <div class="result-tools">
        <input
          v-model="resultKeyword"
          class="result-search"
          type="search"
          placeholder="本頁篩選代號／名稱"
          enterkeyhint="search"
        />
        <button
          type="button"
          class="ghost export-btn"
          :disabled="loading || exporting || !total"
          @click="exportExcel"
        >
          {{ exporting ? '匯出中…' : '匯出 Excel' }}
        </button>
        <span class="page-ctrl">
          <button type="button" class="page-btn" :disabled="form.page <= 1 || loading" @click="goPage(-1)">上一頁</button>
          <span>{{ form.page }} / {{ totalPages }}</span>
          <button type="button" class="page-btn" :disabled="form.page >= totalPages || loading" @click="goPage(1)">下一頁</button>
        </span>
      </div>
    </div>

    <div class="table-shell">
      <table>
        <thead>
          <tr>
            <th class="sticky">股票</th>
            <th>市場</th>
            <th>產業</th>
            <th class="num sortable" @click="toggleSort('roe')">ROE{{ sortMark('roe') }}</th>
            <th class="num sortable" @click="toggleSort('roa')">ROA{{ sortMark('roa') }}</th>
            <th class="num sortable" @click="toggleSort('gross_margin')">毛利率{{ sortMark('gross_margin') }}</th>
            <th class="num sortable" @click="toggleSort('op_margin')">營業利益率{{ sortMark('op_margin') }}</th>
            <th class="num sortable" @click="toggleSort('net_margin')">淨利率{{ sortMark('net_margin') }}</th>
            <th class="num sortable" @click="toggleSort('debt_ratio')">負債比{{ sortMark('debt_ratio') }}</th>
            <th class="num sortable" @click="toggleSort('current_ratio')">流動比{{ sortMark('current_ratio') }}</th>
            <th class="num sortable" @click="toggleSort('revenue')">營收{{ sortMark('revenue') }}</th>
            <th class="num sortable" @click="toggleSort('pe')">本益比{{ sortMark('pe') }}</th>
            <th class="num sortable" @click="toggleSort('pb')">淨值比{{ sortMark('pb') }}</th>
            <th class="num sortable" @click="toggleSort('dy')">殖利率{{ sortMark('dy') }}</th>
            <th
              v-for="column in ADVANCED_RESULT_COLUMNS"
              :key="column.key"
              class="num sortable"
              @click="toggleSort(column.key)"
            >
              {{ column.label }}{{ sortMark(column.key) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!loading && !filteredItems.length">
            <td :colspan="resultColumnCount" class="empty muted">沒有符合條件的股票，請放寬條件後再試</td>
          </tr>
          <tr
            v-for="row in filteredItems"
            :key="row.code"
            class="row"
            @click="openStock(row)"
          >
            <td class="sticky stock">
              <span class="code mono">{{ row.code }}</span>
              <span class="name">{{ row.name }}</span>
            </td>
            <td>{{ marketLabel(row.market) }}</td>
            <td>{{ row.industry || '—' }}</td>
            <td class="num mono">{{ formatRatio('roe', row.roe) }}</td>
            <td class="num mono">{{ formatRatio('roa', row.roa) }}</td>
            <td class="num mono">{{ formatRatio('gross_margin', row.gross_margin) }}</td>
            <td class="num mono">{{ formatRatio('op_margin', row.op_margin) }}</td>
            <td class="num mono">{{ formatRatio('net_margin', row.net_margin) }}</td>
            <td class="num mono">{{ formatRatio('debt_ratio', row.debt_ratio) }}</td>
            <td class="num mono">{{ formatRatio('current_ratio', row.current_ratio) }}</td>
            <td class="num mono">{{ formatMoney(row.revenue) }}</td>
            <td class="num mono">{{ row.pe != null ? row.pe.toFixed(1) : '—' }}</td>
            <td class="num mono">{{ row.pb != null ? row.pb.toFixed(2) : '—' }}</td>
            <td class="num mono">{{ row.dy != null ? `${row.dy.toFixed(1)}%` : '—' }}</td>
            <td
              v-for="column in ADVANCED_RESULT_COLUMNS"
              :key="column.key"
              class="num mono"
            >
              {{ formatResultValue(row, column) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    </template>
  </section>
</template>

<style scoped>
.screener {
  min-height: 100vh;
  min-height: 100dvh;
  padding: clamp(0.85rem, 2.5vw, 1.75rem);
  padding-bottom: calc(clamp(0.85rem, 2.5vw, 1.75rem) + env(safe-area-inset-bottom));
  max-width: 1400px;
  margin: 0 auto;
  min-width: 0;
}

.bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.65rem 1rem;
  row-gap: 0.65rem;
  margin-bottom: 1.25rem;
  min-width: 0;
}

.bar-nav {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
}

.nav-sep {
  color: var(--muted);
  opacity: 0.55;
  font-size: 0.75rem;
}

.bar-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  flex-shrink: 0;
  margin-left: auto;
}

.btn-engine__short { display: none; }

.brand-line {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.brand-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  object-fit: cover;
  background: #0a0e14;
}

.brand-title {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 1.35rem;
}

.brand-title__name {
  font-weight: 700;
  color: #e8eef8;
}

.brand-title__tag {
  font-weight: 600;
  color: var(--aqua);
}

.spacer { flex: 1; }

.intro h1 {
  margin: 0;
  font-size: clamp(1.5rem, 3vw, 2.1rem);
}

.intro p {
  margin: 0.4rem 0 0;
  font-size: 0.9rem;
}

.pro-badge {
  display: inline-block;
  margin-top: 0.55rem;
  padding: 0.15rem 0.5rem;
  border: 1px solid rgba(45, 212, 191, 0.35);
  border-radius: 999px;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  color: var(--aqua);
}

.pro-gate {
  margin-top: 1.5rem;
  padding: clamp(1.25rem, 3vw, 2rem);
  border: 1px solid rgba(45, 212, 191, 0.28);
  background:
    linear-gradient(160deg, rgba(45, 212, 191, 0.1), transparent 55%),
    rgba(10, 12, 18, 0.65);
  max-width: 36rem;
}

.pro-gate__eyebrow {
  margin: 0;
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  color: var(--aqua);
}

.pro-gate__title {
  margin: 0.55rem 0 0;
  font-family: var(--display);
  font-size: clamp(1.25rem, 3vw, 1.6rem);
  font-weight: 700;
}

.pro-gate__msg {
  margin: 0.65rem 0 0;
  font-size: 0.92rem;
  line-height: 1.55;
}

.pro-gate__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 1.25rem;
}

a.pro-gate__link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  padding: 0.7rem 1.15rem;
}

.presets {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.65rem;
  margin: 1.25rem 0 1rem;
}

.preset {
  display: grid;
  gap: 0.25rem;
  text-align: left;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--line);
  background: rgba(10, 12, 18, 0.45);
}

.preset.active {
  border-color: rgba(45, 212, 191, 0.45);
  background: rgba(45, 212, 191, 0.1);
}

.preset-label {
  font-weight: 600;
  font-size: 0.92rem;
}

.preset-desc {
  font-size: 0.72rem;
  line-height: 1.35;
}

.filters {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.65rem;
  padding: 0.9rem;
  border: 1px solid var(--line);
  background: rgba(10, 12, 18, 0.45);
  margin-bottom: 0.85rem;
}

.filters label {
  display: grid;
  gap: 0.3rem;
  font-size: 0.75rem;
  color: var(--muted);
}

.filters input,
.filters select {
  width: 100%;
  padding: 0.45rem 0.55rem;
  border: 1px solid var(--line);
  background: rgba(8, 10, 14, 0.85);
  color: var(--paper);
  font-size: 0.88rem;
}

.check-label .check-row {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  min-height: 2.2rem;
  color: var(--paper);
  font-size: 0.82rem;
}

.check-hint {
  color: var(--muted);
  font-size: 0.75rem;
}

.filter-group {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.65rem;
  min-width: 0;
  margin: 0;
  padding: 0.75rem;
  border: 1px solid rgba(45, 212, 191, 0.18);
}

.filter-group legend {
  padding: 0 0.4rem;
  color: var(--aqua);
  font-size: 0.78rem;
  letter-spacing: 0.08em;
}

.filter-actions {
  grid-column: 1 / -1;
  display: flex;
  gap: 0.65rem;
  justify-content: flex-end;
}

.result-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.65rem;
  font-size: 0.82rem;
  margin-bottom: 0.5rem;
}

.result-tools {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.result-search {
  width: min(12rem, 42vw);
  padding: 0.35rem 0.55rem;
  border: 1px solid var(--line);
  background: rgba(8, 10, 14, 0.85);
  color: var(--paper);
  font-size: 0.82rem;
}

.export-btn {
  font-size: 0.78rem;
  padding: 0.3rem 0.65rem;
}

.page-ctrl {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
}

.page-btn {
  padding: 0.25rem 0.55rem;
  font-size: 0.78rem;
}

.table-shell {
  border: 1px solid var(--line);
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  max-height: min(65vh, 640px);
  background: rgba(10, 12, 18, 0.55);
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 3200px;
}

th, td {
  padding: 0.65rem 0.7rem;
  border-bottom: 1px solid rgba(232, 228, 220, 0.06);
  font-size: 0.84rem;
}

thead th {
  position: sticky;
  top: 0;
  background: #10151f;
  color: var(--muted);
  font-weight: 500;
  z-index: 2;
}

th.sortable {
  cursor: pointer;
  user-select: none;
}

th.sortable:hover { color: var(--aqua); }

.sticky {
  position: sticky;
  left: 0;
  background: #0c1018;
  z-index: 1;
}

thead .sticky {
  z-index: 3;
  background: #10151f;
}

.num { text-align: right; }

.row {
  cursor: pointer;
}

.row:hover td {
  background: rgba(45, 212, 191, 0.06);
}

.stock {
  display: grid;
  gap: 0.1rem;
  min-width: 120px;
}

.code {
  color: var(--aqua);
  font-weight: 600;
}

.name {
  font-size: 0.78rem;
  color: var(--muted);
}

.empty {
  text-align: center;
  padding: 2.5rem 1rem;
}

.error {
  color: var(--down);
  border: 1px solid rgba(224, 122, 106, 0.35);
  background: rgba(224, 122, 106, 0.08);
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
}

@media (max-width: 1023px) {
  .presets { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filter-group { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .brand-title { font-size: 1.15rem; }
}

@media (max-width: 767px) {
  .bar {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas:
      "brand actions"
      "nav nav";
    gap: 0.55rem 0.65rem;
    margin-bottom: 1rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--line);
  }

  .spacer { display: none; }

  .brand-line {
    grid-area: brand;
  }

  .bar-actions {
    grid-area: actions;
    margin-left: 0;
    justify-content: flex-end;
  }

  .bar-nav {
    grid-area: nav;
    width: 100%;
    gap: 0.15rem;
    padding-top: 0.15rem;
  }

  .brand-title {
    font-size: 1.08rem;
    gap: 6px;
  }

  .brand-title__name { display: none; }

  .brand-icon {
    width: 34px;
    height: 34px;
  }

  .btn-engine {
    min-height: 40px;
    padding: 0.45rem 0.85rem;
  }

  .btn-engine__full { display: none; }
  .btn-engine__short { display: inline; }

  .presets {
    grid-template-columns: 1fr;
  }

  .filters {
    grid-template-columns: 1fr;
    padding: 0.75rem;
  }

  .filter-group {
    grid-template-columns: 1fr;
    padding: 0.65rem;
  }

  .filters input,
  .filters select {
    min-height: 44px;
    font-size: 1rem;
  }

  .filter-actions {
    justify-content: stretch;
  }

  .filter-actions button {
    flex: 1;
    min-height: 44px;
  }

  .result-bar {
    flex-wrap: wrap;
    gap: 0.55rem;
  }

  .result-search {
    width: 100%;
    min-height: 40px;
  }

  .page-btn {
    min-height: 40px;
    min-width: 40px;
    padding: 0.4rem 0.65rem;
  }
}
</style>
