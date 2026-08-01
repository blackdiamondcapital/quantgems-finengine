<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import { formatMoney, formatRatio } from '../utils/format'
import AuthBar from './AuthBar.vue'
import { MAIN_SITE_URL } from '../lib/siteLinks'

const emit = defineEmits(['open-stock', 'goto-engine', 'back'])

const loading = ref(false)
const error = ref('')
const meta = ref(null)
const result = ref(null)

const form = reactive({
  preset: 'high_roe',
  market: 'both',
  industry: '',
  period: 'latest',
  roe_min: '',
  gross_margin_min: '',
  debt_ratio_max: '',
  current_ratio_min: '',
  pe_max: '',
  pb_max: '',
  dy_min: '',
  sort: 'roe',
  dir: 'desc',
  page: 1,
})

const presets = computed(() => meta.value?.presets || result.value?.presets || [])
const industries = computed(() => meta.value?.industries || [])
const periods = computed(() => meta.value?.periods || [])
const items = computed(() => result.value?.items || [])
const total = computed(() => result.value?.total || 0)
const pageSize = computed(() => result.value?.pageSize || 50)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

function pctInputToRatio(v) {
  if (v === '' || v == null) return undefined
  const n = Number(v)
  if (Number.isNaN(n)) return undefined
  // 使用者輸入百分比：15 → 0.15
  return n > 1 || n < -1 ? n / 100 : n
}

function buildQuery() {
  const q = {
    market: form.market,
    industry: form.industry || undefined,
    period: form.period || 'latest',
    sort: form.sort,
    dir: form.dir,
    page: form.page,
    page_size: 50,
  }

  if (form.preset) q.preset = form.preset

  const roeMin = pctInputToRatio(form.roe_min)
  const gmMin = pctInputToRatio(form.gross_margin_min)
  const debtMax = pctInputToRatio(form.debt_ratio_max)
  if (roeMin != null) q.roe_min = roeMin
  if (gmMin != null) q.gross_margin_min = gmMin
  if (debtMax != null) q.debt_ratio_max = debtMax
  if (form.current_ratio_min !== '') q.current_ratio_min = Number(form.current_ratio_min)
  if (form.pe_max !== '') q.pe_max = Number(form.pe_max)
  if (form.pb_max !== '') q.pb_max = Number(form.pb_max)
  if (form.dy_min !== '') q.dy_min = Number(form.dy_min)

  return q
}

async function loadMeta() {
  try {
    meta.value = await api.screenerMeta()
  } catch {
    meta.value = null
  }
}

async function runScreen() {
  loading.value = true
  error.value = ''
  try {
    result.value = await api.screener(buildQuery())
  } catch (e) {
    error.value = e?.message || '選股失敗'
    result.value = null
  } finally {
    loading.value = false
  }
}

function applyPreset(id) {
  form.preset = form.preset === id ? '' : id
  form.page = 1
  // 套用策略時清空手動覆寫，避免混淆；仍可用下方欄位再加嚴
  if (form.preset) {
    form.roe_min = ''
    form.gross_margin_min = ''
    form.debt_ratio_max = ''
    form.current_ratio_min = ''
    form.pe_max = ''
    form.pb_max = ''
    form.dy_min = ''
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
  form.roe_min = ''
  form.gross_margin_min = ''
  form.debt_ratio_max = ''
  form.current_ratio_min = ''
  form.pe_max = ''
  form.pb_max = ''
  form.dy_min = ''
  form.sort = 'roe'
  form.dir = 'desc'
  form.page = 1
  runScreen()
}

function toggleSort(key) {
  if (form.sort === key) {
    form.dir = form.dir === 'desc' ? 'asc' : 'desc'
  } else {
    form.sort = key
    form.dir = key === 'debt_ratio' || key === 'pe' || key === 'pb' ? 'asc' : 'desc'
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

watch(
  () => form.market,
  () => {
    form.page = 1
  },
)

onMounted(async () => {
  await loadMeta()
  await runScreen()
})
</script>

<template>
  <section class="screener">
    <header class="bar">
      <a class="home-link" :href="MAIN_SITE_URL" target="_blank" rel="noopener noreferrer">QuantGems® 主站</a>
      <button class="nav-back" type="button" @click="$emit('back')">← 首頁</button>
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
      <button class="ghost" type="button" @click="$emit('goto-engine')">財報工作台</button>
      <AuthBar />
    </header>

    <div class="intro">
      <h1 class="display">財務選股</h1>
      <p class="muted">
        以季報財務比率篩選台股；點選股票可進入財報引擎查看完整報表。
        <span v-if="result?.periodLabel">資料期別 {{ result.periodLabel }}</span>
      </p>
    </div>

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
        <span>毛利率 ≥ %</span>
        <input v-model="form.gross_margin_min" type="number" step="0.1" placeholder="例 30" />
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
      <div class="filter-actions">
        <button class="cta" type="submit" :disabled="loading">套用條件</button>
        <button class="ghost" type="button" :disabled="loading" @click="clearFilters">清除</button>
      </div>
    </form>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="result-bar muted">
      <span v-if="loading">篩選中…</span>
      <span v-else>符合 {{ total.toLocaleString('zh-TW') }} 檔</span>
      <span class="page-ctrl">
        <button type="button" class="page-btn" :disabled="form.page <= 1 || loading" @click="goPage(-1)">上一頁</button>
        <span>{{ form.page }} / {{ totalPages }}</span>
        <button type="button" class="page-btn" :disabled="form.page >= totalPages || loading" @click="goPage(1)">下一頁</button>
      </span>
    </div>

    <div class="table-shell">
      <table>
        <thead>
          <tr>
            <th class="sticky">股票</th>
            <th>市場</th>
            <th>產業</th>
            <th class="num sortable" @click="toggleSort('roe')">ROE{{ sortMark('roe') }}</th>
            <th class="num sortable" @click="toggleSort('gross_margin')">毛利率{{ sortMark('gross_margin') }}</th>
            <th class="num sortable" @click="toggleSort('debt_ratio')">負債比{{ sortMark('debt_ratio') }}</th>
            <th class="num sortable" @click="toggleSort('current_ratio')">流動比{{ sortMark('current_ratio') }}</th>
            <th class="num sortable" @click="toggleSort('revenue')">營收{{ sortMark('revenue') }}</th>
            <th class="num sortable" @click="toggleSort('pe')">本益比{{ sortMark('pe') }}</th>
            <th class="num sortable" @click="toggleSort('dy')">殖利率{{ sortMark('dy') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!loading && !items.length">
            <td colspan="10" class="empty muted">沒有符合條件的股票，請放寬條件後再試</td>
          </tr>
          <tr
            v-for="row in items"
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
            <td class="num mono">{{ formatRatio('gross_margin', row.gross_margin) }}</td>
            <td class="num mono">{{ formatRatio('debt_ratio', row.debt_ratio) }}</td>
            <td class="num mono">{{ formatRatio('current_ratio', row.current_ratio) }}</td>
            <td class="num mono">{{ formatMoney(row.revenue) }}</td>
            <td class="num mono">{{ row.pe != null ? row.pe.toFixed(1) : '—' }}</td>
            <td class="num mono">{{ row.dy != null ? `${row.dy.toFixed(1)}%` : '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.screener {
  min-height: 100vh;
  min-height: 100dvh;
  padding: clamp(1rem, 2.5vw, 1.75rem);
  max-width: 1280px;
  margin: 0 auto;
}

.bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.brand-line {
  display: flex;
  align-items: center;
  gap: 8px;
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

.presets {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
  font-size: 0.82rem;
  margin-bottom: 0.5rem;
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
  max-height: min(65vh, 640px);
  background: rgba(10, 12, 18, 0.55);
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 960px;
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

@media (max-width: 960px) {
  .presets { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
