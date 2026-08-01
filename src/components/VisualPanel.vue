<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { formatMoney, formatRatio } from '../utils/format'

const props = defineProps({
  kind: { type: String, default: 'income' },
  payload: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  incomeBasis: { type: String, default: 'single' },
})

const COLORS = ['#2dd4bf', '#d4a574', '#e8e4dc', '#e07a6a', '#7aa2ff', '#c4b5fd', '#fbbf24', '#67e8f9']
const MAX_SERIES = 8

const PRESET_DEFAULTS = {
  income: ['Revenue', 'ProfitLossFromOperatingActivities', 'ProfitLoss'],
  balance: ['Assets', 'Liabilities', 'Equity'],
  cashflow: [
    'NetCashFlowsFromUsedInOperatingActivities',
    'NetCashFlowsFromUsedInInvestingActivities',
    'NetCashFlowsFromUsedInFinancingActivities',
  ],
  combined: [
    'Revenue',
    'ProfitLoss',
    'Assets',
    'Equity',
    'NetCashFlowsFromUsedInOperatingActivities',
  ],
  ratios: ['gross_margin', 'op_margin', 'net_margin', 'roe', 'debt_ratio'],
}

const query = ref('')
const selectedKeys = ref([])
const el = ref(null)
let chart = null

const periods = computed(() => {
  const list = props.payload?.periods || []
  return [...list].reverse()
})

const fieldGroups = computed(() => {
  const q = query.value.trim().toLowerCase()
  const groups = []
  for (const sec of props.payload?.sections || []) {
    const items = (sec.items || []).filter((item) => {
      if (!q) return true
      return (
        item.label?.toLowerCase().includes(q) ||
        item.key?.toLowerCase().includes(q)
      )
    })
    if (items.length) {
      groups.push({
        id: sec.id,
        section: sec.section,
        items,
      })
    }
  }
  return groups
})

const allFields = computed(() => {
  const list = []
  for (const sec of props.payload?.sections || []) {
    for (const item of sec.items || []) list.push(item)
  }
  return list
})

const fieldMap = computed(() => {
  const map = {}
  for (const item of allFields.value) map[item.key] = item
  return map
})

const fieldTotal = computed(() => allFields.value.length)

const selectedCount = computed(() => selectedKeys.value.length)

const selectedFields = computed(() =>
  selectedKeys.value
    .map((key) => fieldMap.value[key])
    .filter(Boolean),
)

function seriesValues(key) {
  const item = fieldMap.value[key]
  if (!item) return periods.value.map(() => null)
  return periods.value.map((p) => {
    const v = item.values?.[p.value]
    return v == null || Number.isNaN(Number(v)) ? null : Number(v)
  })
}

const chartMode = computed(() => {
  const fields = selectedFields.value
  if (!fields.length) return 'money'
  if (fields.every((f) => f.isRatio)) return 'ratio'
  if (fields.every((f) => f.isEps)) return 'eps'
  return 'money'
})

const chartSeries = computed(() =>
  selectedFields.value.map((item) => ({
    key: item.key,
    name: item.label || item.key,
    type: 'line',
    isEps: !!item.isEps,
    data: seriesValues(item.key),
  })),
)

const hasData = computed(() =>
  chartSeries.value.some((s) => s.data.some((v) => v != null)),
)

function axisMoney(v) {
  const a = Math.abs(v)
  if (a >= 1e12) return `${(v / 1e12).toFixed(1)}兆`
  if (a >= 1e8) return `${(v / 1e8).toFixed(0)}億`
  if (a >= 1e4) return `${(v / 1e4).toFixed(0)}萬`
  return String(v)
}

function formatTooltipValue(item, value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  if (item?.isRatio || chartMode.value === 'ratio') return formatRatio(item?.key, value)
  if (item?.isEps || chartMode.value === 'eps') return formatMoney(value, { isEps: true })
  return formatMoney(value)
}

function applyDefaultSelection() {
  const available = new Set(allFields.value.map((f) => f.key))
  if (!available.size) {
    selectedKeys.value = []
    return
  }
  const presets = (PRESET_DEFAULTS[props.kind] || []).filter((k) => available.has(k))
  if (presets.length) {
    selectedKeys.value = presets.slice(0, MAX_SERIES)
    return
  }
  selectedKeys.value = [allFields.value[0].key]
}

function toggleKey(key) {
  const idx = selectedKeys.value.indexOf(key)
  if (idx >= 0) {
    selectedKeys.value = selectedKeys.value.filter((k) => k !== key)
    return
  }
  if (selectedKeys.value.length >= MAX_SERIES) return
  selectedKeys.value = [...selectedKeys.value, key]
}

function isSelected(key) {
  return selectedKeys.value.includes(key)
}

function clearSelection() {
  selectedKeys.value = []
}

function selectSection(sec) {
  const keys = sec.items.map((i) => i.key)
  const next = [...selectedKeys.value]
  for (const key of keys) {
    if (next.includes(key)) continue
    if (next.length >= MAX_SERIES) break
    next.push(key)
  }
  selectedKeys.value = next
}

function render() {
  if (!el.value || props.loading) return
  if (!chart) chart = echarts.init(el.value, null, { renderer: 'canvas' })

  if (!selectedFields.value.length || !hasData.value) {
    chart.clear()
    return
  }

  const labels = periods.value.map((p) => p.label || p.value)
  const mode = chartMode.value
  const series = chartSeries.value.map((s, idx) => {
    const color = COLORS[idx % COLORS.length]
    return {
      name: s.name,
      type: 'line',
      data: s.data,
      smooth: 0.25,
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: { color },
      lineStyle: { color, width: 2 },
    }
  })

  chart.setOption(
    {
      backgroundColor: 'transparent',
      animationDuration: 550,
      grid: { left: 56, right: 28, top: 44, bottom: 36 },
      legend: {
        top: 0,
        type: 'scroll',
        textStyle: { color: '#8b929e', fontFamily: 'Noto Sans TC', fontSize: 11 },
        itemWidth: 12,
        itemHeight: 8,
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#10151f',
        borderColor: 'rgba(45,212,191,0.28)',
        textStyle: { color: '#e8e4dc', fontFamily: 'Noto Sans TC' },
        formatter: (params) => {
          const rows = Array.isArray(params) ? params : [params]
          const head = rows[0]?.axisValueLabel || ''
          const body = rows
            .map((p) => {
              const field = selectedFields.value[p.seriesIndex]
              return `${p.marker}${p.seriesName}：${formatTooltipValue(field, p.value)}`
            })
            .join('<br/>')
          return `${head}<br/>${body}`
        },
      },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { lineStyle: { color: 'rgba(232,228,220,0.12)' } },
        axisLabel: { color: '#8b929e', fontFamily: 'JetBrains Mono', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(232,228,220,0.06)' } },
        axisLabel: {
          color: '#8b929e',
          fontFamily: 'JetBrains Mono',
          fontSize: 10,
          formatter: (v) => {
            if (mode === 'ratio') {
              const first = selectedFields.value[0]
              if (first?.isMultiple) return Number(v).toFixed(2)
              const pct = Math.abs(v) <= 5 ? v * 100 : v
              return `${pct.toFixed(0)}%`
            }
            if (mode === 'eps') return Number(v).toFixed(1)
            return axisMoney(v)
          },
        },
      },
      series,
    },
    true,
  )
}

function onResize() {
  chart?.resize()
}

watch(
  () => props.kind,
  () => {
    applyDefaultSelection()
  },
)

watch(
  () => props.payload,
  () => {
    const available = new Set(allFields.value.map((f) => f.key))
    selectedKeys.value = selectedKeys.value.filter((k) => available.has(k))
    if (!selectedKeys.value.length && available.size) applyDefaultSelection()
  },
)

watch(
  [() => props.payload, selectedKeys, () => props.loading, () => props.incomeBasis],
  async () => {
    await nextTick()
    render()
  },
  { deep: true },
)

onMounted(() => {
  applyDefaultSelection()
  render()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div class="visual">
    <aside class="menu" aria-label="科目選單">
      <div class="menu-head">
        <p class="menu-title muted">全部科目</p>
        <p class="menu-meta muted mono">
          已選 {{ selectedCount }}/{{ MAX_SERIES }} · 共 {{ fieldTotal }}
        </p>
      </div>

      <input
        v-model="query"
        class="search"
        type="search"
        placeholder="搜尋科目…"
        aria-label="搜尋科目"
      />

      <div class="menu-actions">
        <button type="button" class="link-btn" @click="clearSelection">清除選取</button>
      </div>

      <div class="menu-scroll">
        <div v-if="loading" class="menu-empty muted">載入科目中…</div>
        <div v-else-if="!fieldGroups.length" class="menu-empty muted">
          {{ query ? '找不到符合的科目' : '尚無科目' }}
        </div>
        <template v-else>
          <section v-for="sec in fieldGroups" :key="sec.id" class="field-section">
            <div class="section-head">
              <span>{{ sec.section }}</span>
              <button type="button" class="link-btn" @click="selectSection(sec)">加入</button>
            </div>
            <label
              v-for="item in sec.items"
              :key="item.key"
              class="field-item"
              :class="{ active: isSelected(item.key), disabled: !isSelected(item.key) && selectedCount >= MAX_SERIES }"
            >
              <input
                type="checkbox"
                :checked="isSelected(item.key)"
                :disabled="!isSelected(item.key) && selectedCount >= MAX_SERIES"
                @change="toggleKey(item.key)"
              />
              <span class="field-label">{{ item.label }}</span>
            </label>
          </section>
        </template>
      </div>
    </aside>

    <div class="canvas-wrap">
      <div class="head">
        <div>
          <h3 class="display">科目趨勢</h3>
          <p class="muted sub">
            <span v-if="selectedFields.length">{{ selectedFields.map((f) => f.label).join('、') }}</span>
            <span v-else>請從左側勾選科目</span>
            <span v-if="kind === 'income' || kind === 'combined' || kind === 'ratios'">
              · {{ incomeBasis === 'cumulative' ? '累計' : '單季' }}
            </span>
            <span v-if="periods.length"> · {{ periods.length }} 期</span>
          </p>
        </div>
      </div>

      <div v-if="loading" class="state muted">讀取圖表資料中…</div>
      <div v-else-if="!payload || !periods.length" class="state muted">尚無此報表資料</div>
      <div v-else-if="!selectedFields.length" class="state muted">請勾選至少一個科目</div>
      <div v-else-if="!hasData" class="state muted">所選科目在此區間暫無資料</div>
      <div v-show="!loading && selectedFields.length && hasData" ref="el" class="chart" />
    </div>
  </div>
</template>

<style scoped>
.visual {
  display: grid;
  grid-template-columns: minmax(220px, 280px) 1fr;
  gap: 0;
  border: 1px solid var(--line);
  background: rgba(10, 12, 18, 0.55);
  min-height: 420px;
}

.menu {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 0.85rem 0.65rem;
  border-right: 1px solid var(--line);
  background: rgba(8, 10, 14, 0.55);
  min-height: 0;
}

.menu-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0 0.35rem;
}

.menu-title {
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  margin: 0;
}

.menu-meta {
  font-size: 0.68rem;
  margin: 0;
}

.search {
  width: 100%;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--line);
  background: rgba(8, 10, 14, 0.85);
  color: var(--paper);
  font-size: 0.84rem;
}

.search:focus {
  outline: none;
  border-color: rgba(45, 212, 191, 0.45);
}

.menu-actions {
  display: flex;
  justify-content: flex-end;
  padding: 0 0.2rem;
}

.link-btn {
  border: none;
  background: transparent;
  color: var(--aqua);
  font-size: 0.72rem;
  padding: 0.1rem 0.2rem;
}

.menu-scroll {
  overflow: auto;
  min-height: 0;
  max-height: min(62vh, 560px);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding-right: 0.15rem;
}

.menu-empty {
  padding: 1.5rem 0.5rem;
  text-align: center;
  font-size: 0.84rem;
}

.field-section {
  display: grid;
  gap: 0.2rem;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.4rem;
  color: var(--aqua);
  font-size: 0.75rem;
  letter-spacing: 0.1em;
  border-bottom: 1px solid rgba(45, 212, 191, 0.15);
  margin-bottom: 0.15rem;
}

.field-item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.5rem;
  align-items: start;
  padding: 0.45rem 0.5rem;
  border: 1px solid transparent;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 0.84rem;
  line-height: 1.35;
}

.field-item:hover {
  background: rgba(45, 212, 191, 0.06);
}

.field-item.active {
  background: rgba(45, 212, 191, 0.12);
  border-color: rgba(45, 212, 191, 0.28);
}

.field-item.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.field-item input {
  margin-top: 0.15rem;
}

.field-label {
  min-width: 0;
}

.canvas-wrap {
  min-width: 0;
  padding: 1rem 1rem 0.75rem;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 0.35rem;
}

.head h3 {
  margin: 0;
  font-size: 1.05rem;
  letter-spacing: 0.06em;
}

.sub {
  margin: 0.25rem 0 0;
  font-size: 0.78rem;
  line-height: 1.45;
}

.state {
  display: grid;
  place-items: center;
  min-height: 300px;
  text-align: center;
  padding: 1rem;
}

.chart {
  width: 100%;
  height: min(52vh, 420px);
  min-height: 300px;
}

@media (max-width: 820px) {
  .visual {
    grid-template-columns: 1fr;
  }

  .menu {
    border-right: none;
    border-bottom: 1px solid var(--line);
  }

  .menu-scroll {
    max-height: 240px;
  }
}
</style>
