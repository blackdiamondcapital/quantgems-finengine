<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import SymbolSearch from './SymbolSearch.vue'
import HighlightStrip from './HighlightStrip.vue'
import StatementTable from './StatementTable.vue'
import VisualPanel from './VisualPanel.vue'
import AuthBar from './AuthBar.vue'
import { MAIN_SITE_URL } from '../lib/siteLinks'

const props = defineProps({
  seedCode: { type: String, default: '2330' },
})
defineEmits(['back', 'goto-screener'])

const code = ref(props.seedCode || '2330')
const symbol = ref(null)
const overview = ref(null)
const kind = ref('income')
const statement = ref(null)
const fieldMeta = ref(null)
const showAllFields = ref(false)
const incomeBasis = ref('single')
const viewMode = ref('table')
const loadingOverview = ref(false)
const loadingStatement = ref(false)
const error = ref('')

const tabDefs = [
  { id: 'income', label: '損益表' },
  { id: 'balance', label: '資產負債' },
  { id: 'cashflow', label: '現金流量' },
  { id: 'ratios', label: '財務比率' },
  { id: 'combined', label: '綜合報表' },
]

const tabs = computed(() =>
  tabDefs.map((t) => ({
    ...t,
    count: fieldMeta.value?.fieldCounts?.[t.id] ?? null,
  })),
)

const statementLimit = computed(() => (viewMode.value === 'visual' ? 12 : 8))
const statementFull = computed(
  () => viewMode.value === 'visual' || showAllFields.value,
)

async function loadMeta() {
  try {
    fieldMeta.value = await api.meta()
  } catch {
    fieldMeta.value = null
  }
}

async function loadAll(nextCode) {
  const c = (nextCode || code.value || '').trim()
  if (!c) return
  code.value = c
  error.value = ''
  loadingOverview.value = true
  loadingStatement.value = true
  try {
    const ov = await api.overview(c, { basis: incomeBasis.value })
    overview.value = ov
    symbol.value = ov.symbol
    const st = await api.statement(c, kind.value, statementLimit.value, {
      full: statementFull.value,
      basis: incomeBasis.value,
    })
    statement.value = st
  } catch (e) {
    error.value = e?.message || '載入失敗'
    overview.value = null
    statement.value = null
  } finally {
    loadingOverview.value = false
    loadingStatement.value = false
  }
}

async function loadStatement() {
  if (!code.value) return
  loadingStatement.value = true
  error.value = ''
  try {
    statement.value = await api.statement(code.value, kind.value, statementLimit.value, {
      full: statementFull.value,
      basis: incomeBasis.value,
    })
  } catch (e) {
    error.value = e?.message || '報表載入失敗'
    statement.value = null
  } finally {
    loadingStatement.value = false
  }
}

function onSelect(item) {
  loadAll(item.code)
}

function onToggleFull(checked) {
  showAllFields.value = checked
  loadStatement()
}

async function reloadOverview() {
  if (!code.value) return
  loadingOverview.value = true
  try {
    overview.value = await api.overview(code.value, { basis: incomeBasis.value })
  } catch (e) {
    error.value = e?.message || '概覽載入失敗'
  } finally {
    loadingOverview.value = false
  }
}

function setIncomeBasis(next) {
  if (incomeBasis.value === next) return
  incomeBasis.value = next
  reloadOverview()
  if (kind.value === 'income' || kind.value === 'combined' || kind.value === 'ratios') {
    loadStatement()
  }
}

function setViewMode(next) {
  if (viewMode.value === next) return
  const prevLimit = statementLimit.value
  const prevFull = statementFull.value
  viewMode.value = next
  if (statementLimit.value !== prevLimit || statementFull.value !== prevFull) {
    loadStatement()
  }
}

watch(kind, () => {
  loadStatement()
})

onMounted(async () => {
  await loadMeta()
  loadAll(props.seedCode || '2330')
})
</script>

<template>
  <section class="engine">
    <header class="bar">
      <div class="bar-nav">
        <a class="home-link" :href="MAIN_SITE_URL" target="_blank" rel="noopener noreferrer">
          <span class="home-link__full">QuantGems® 主站</span>
          <span class="home-link__short">主站</span>
        </a>
        <span class="nav-sep" aria-hidden="true">·</span>
        <button class="nav-back" type="button" @click="$emit('back')">← 首頁</button>
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
          <span class="brand-title__tag">財報引擎</span>
        </span>
      </div>
      <div class="spacer" />
      <div class="bar-actions">
        <button class="btn-screener" type="button" @click="$emit('goto-screener')">
          <span class="btn-screener__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M4 5h16l-6.2 7.4V18l-3.6 2v-7.6L4 5z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
              <circle cx="17.2" cy="7.2" r="1.35" fill="currentColor"/>
            </svg>
          </span>
          <span class="btn-screener__label">選股</span>
          <span class="btn-screener__pro">Pro</span>
          <span class="btn-screener__spark" aria-hidden="true" />
        </button>
        <AuthBar />
      </div>
    </header>

    <div class="search-block">
      <SymbolSearch :initial="code" @select="onSelect" />
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="symbol" class="identity anim-rise">
      <div>
        <h1 class="display">
          <span class="code mono">{{ symbol.code }}</span>
          {{ symbol.label }}
        </h1>
        <p class="muted meta">
          <span v-if="symbol.market">{{ symbol.market }}</span>
          <span v-if="symbol.industry"> · {{ symbol.industry }}</span>
          <span v-if="overview?.latestPeriod"> · 最新 {{ overview.latestPeriod }}</span>
        </p>
      </div>
      <p class="tagline muted">季報切面 · 多期對照</p>
    </div>

    <HighlightStrip
      v-if="overview?.highlight"
      :highlight="overview.highlight"
      :ratios="overview.ratios"
    />

    <div class="statement-pane">
        <div class="tabs">
          <button
            v-for="t in tabs"
            :key="t.id"
            class="tab"
            :class="{ active: kind === t.id }"
            type="button"
            @click="kind = t.id"
          >
            {{ t.label }}
            <span v-if="t.count" class="tab-count mono">{{ t.count }}</span>
          </button>
        </div>
        <div class="toolbar-row">
          <div class="view-bar">
            <span class="basis-label muted">顯示模式</span>
            <div class="basis-toggle">
              <button
                type="button"
                class="basis-btn"
                :class="{ active: viewMode === 'table' }"
                @click="setViewMode('table')"
              >
                表格
              </button>
              <button
                type="button"
                class="basis-btn"
                :class="{ active: viewMode === 'visual' }"
                @click="setViewMode('visual')"
              >
                視覺化
              </button>
            </div>
          </div>
          <div
            v-if="kind === 'income' || kind === 'combined' || kind === 'ratios'"
            class="basis-bar"
          >
            <span class="basis-label muted">
              {{ kind === 'ratios' ? '比率計算' : '損益表顯示' }}
            </span>
            <div class="basis-toggle">
              <button
                type="button"
                class="basis-btn"
                :class="{ active: incomeBasis === 'single' }"
                @click="setIncomeBasis('single')"
              >
                單季
              </button>
              <button
                type="button"
                class="basis-btn"
                :class="{ active: incomeBasis === 'cumulative' }"
                @click="setIncomeBasis('cumulative')"
              >
                累計
              </button>
            </div>
            <span class="basis-hint muted">
              {{
                kind === 'ratios'
                  ? '毛利率／ROE 等依損益單季或累計重算'
                  : 'Q4 原為全年累計；切換後自動換算'
              }}
            </span>
          </div>
        </div>
        <StatementTable
          v-if="viewMode === 'table'"
          :payload="statement"
          :loading="loadingStatement || loadingOverview"
          :field-total="fieldMeta?.fieldCounts?.[kind]"
          @toggle-full="onToggleFull"
        />
        <VisualPanel
          v-else
          :kind="kind"
          :payload="statement"
          :loading="loadingStatement || loadingOverview"
          :income-basis="incomeBasis"
        />
    </div>
  </section>
</template>

<style scoped>
.engine {
  min-height: 100vh;
  min-height: 100dvh;
  padding: clamp(0.85rem, 2.5vw, 1.75rem);
  padding-bottom: calc(clamp(0.85rem, 2.5vw, 1.75rem) + env(safe-area-inset-bottom));
  max-width: 1280px;
  margin: 0 auto;
  min-width: 0;
}

.bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.65rem 1rem;
  row-gap: 0.65rem;
  margin-bottom: 1.5rem;
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

.brand-line {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.brand-icon {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 10px;
  object-fit: cover;
  display: block;
  background: #0a0e14;
}

.brand-title {
  display: flex;
  align-items: center;
  gap: 9px;
  font-family: var(--sans);
  font-size: 1.35rem;
  line-height: 1.2;
  white-space: nowrap;
}

.brand-title__name {
  font-weight: 700;
  color: #e8eef8;
}

.brand-title__tag {
  font-weight: 600;
  color: var(--aqua);
  letter-spacing: 0.02em;
}

.spacer { flex: 1; }

.btn-screener {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.42rem 0.95rem 0.42rem 0.7rem;
  border: 1px solid rgba(45, 212, 191, 0.45);
  border-radius: 999px;
  background:
    linear-gradient(145deg, rgba(45, 212, 191, 0.22), rgba(45, 212, 191, 0.06) 55%, rgba(212, 165, 116, 0.1));
  color: var(--aqua);
  font-size: 0.88rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  overflow: hidden;
  box-shadow: 0 0 0 0 rgba(45, 212, 191, 0);
  transition:
    transform 0.22s cubic-bezier(0.34, 1.4, 0.64, 1),
    border-color 0.2s,
    box-shadow 0.25s,
    color 0.2s;
}

.btn-screener__icon {
  display: grid;
  place-items: center;
  width: 1.15rem;
  height: 1.15rem;
  border-radius: 999px;
  background: rgba(45, 212, 191, 0.18);
  transition: transform 0.22s cubic-bezier(0.34, 1.4, 0.64, 1);
}

.btn-screener__icon svg {
  width: 0.78rem;
  height: 0.78rem;
}

.btn-screener__label {
  position: relative;
  z-index: 1;
}

.btn-screener__pro {
  position: relative;
  z-index: 1;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 0.08rem 0.32rem;
  border-radius: 999px;
  color: #041311;
  background: linear-gradient(135deg, var(--brass), #e8c9a0);
}

.btn-screener__spark {
  position: absolute;
  top: 0.28rem;
  right: 0.45rem;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--brass);
  opacity: 0.75;
  box-shadow: 0 0 8px rgba(212, 165, 116, 0.75);
  animation: screenerSpark 1.8s ease-in-out infinite;
}

.btn-screener:hover:not(:disabled) {
  transform: translateY(-2px) scale(1.03);
  border-color: rgba(45, 212, 191, 0.85);
  color: #7ef0dc;
  background:
    linear-gradient(145deg, rgba(45, 212, 191, 0.32), rgba(45, 212, 191, 0.1) 55%, rgba(212, 165, 116, 0.16));
  box-shadow: 0 8px 22px rgba(45, 212, 191, 0.18);
}

.btn-screener:hover:not(:disabled) .btn-screener__icon {
  transform: rotate(-12deg) scale(1.08);
}

.btn-screener:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
}

@keyframes screenerSpark {
  0%, 100% { opacity: 0.35; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.15); }
}

@media (prefers-reduced-motion: reduce) {
  .btn-screener,
  .btn-screener__icon {
    transition: none;
  }
  .btn-screener__spark {
    animation: none;
  }
}

.search-block {
  max-width: 560px;
  margin-bottom: 1.5rem;
}

.identity {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

h1 {
  margin: 0;
  font-size: clamp(1.6rem, 3.5vw, 2.4rem);
  letter-spacing: 0.02em;
  font-weight: 700;
}

.code {
  color: var(--aqua);
  margin-right: 0.35rem;
}

.meta {
  margin: 0.35rem 0 0;
  font-size: 0.88rem;
}

.tagline {
  font-family: var(--mono);
  font-size: 0.75rem;
  letter-spacing: 0.08em;
}

.statement-pane {
  display: grid;
  gap: 0.75rem;
  margin-top: 1.25rem;
}

.tabs {
  display: flex;
  flex-wrap: nowrap;
  gap: 1.35rem;
  border-bottom: 1px solid var(--line);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}

.tabs .tab {
  flex: 0 0 auto;
  white-space: nowrap;
}

.tab-count {
  margin-left: 0.35rem;
  font-size: 0.72rem;
  color: var(--muted);
  opacity: 0.85;
}

.tab.active .tab-count {
  color: var(--aqua);
}

.toolbar-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.85rem 1.5rem;
}

.view-bar,
.basis-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.65rem 1rem;
}

.basis-label {
  font-size: 0.78rem;
  letter-spacing: 0.08em;
}

.basis-toggle {
  display: inline-flex;
  border: 1px solid var(--line);
  overflow: hidden;
}

.basis-btn {
  padding: 0.35rem 0.85rem;
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 0.82rem;
  cursor: pointer;
}

.basis-btn + .basis-btn {
  border-left: 1px solid var(--line);
}

.basis-btn.active {
  background: rgba(45, 212, 191, 0.12);
  color: var(--aqua);
}

.basis-hint {
  font-size: 0.72rem;
}

.error {
  color: var(--down);
  border: 1px solid rgba(224, 122, 106, 0.35);
  background: rgba(224, 122, 106, 0.08);
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

@media (max-width: 1023px) {
  .brand-title {
    font-size: 1.15rem;
  }
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
    white-space: nowrap;
    gap: 6px;
  }

  .brand-title__name { display: none; }

  .brand-icon {
    width: 34px;
    height: 34px;
  }

  .btn-screener {
    min-height: 40px;
    padding: 0.4rem 0.85rem 0.4rem 0.65rem;
    font-size: 0.84rem;
  }

  .search-block {
    max-width: none;
    margin-bottom: 1.1rem;
  }

  .identity {
    flex-direction: column;
    align-items: flex-start;
  }

  .tagline {
    order: -1;
  }

  .tabs {
    gap: 0.85rem;
  }

  .tab-count { display: none; }

  .basis-hint {
    width: 100%;
    line-height: 1.4;
  }
}
</style>
