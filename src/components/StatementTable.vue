<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { changeClass, changePct, formatMoney, formatRatio } from '../utils/format'

const props = defineProps({
  payload: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  fieldTotal: { type: Number, default: null },
})

const emit = defineEmits(['toggle-full'])

const query = ref('')
const scrollerRef = ref(null)
const scrollCanLeft = ref(false)
const scrollCanRight = ref(false)
const isMobile = ref(false)

const periods = computed(() => props.payload?.periods || [])
const periodCount = computed(() => periods.value.length)
const showPeriodNav = computed(() => isMobile.value && periodCount.value > 2)

const totalFields = computed(
  () => props.payload?.fieldTotal ?? props.fieldTotal ?? null,
)

const shownFields = computed(() => props.payload?.fieldShown ?? null)

const showAllFields = computed(() => props.payload?.showAllFields ?? false)

const sections = computed(() => {
  const q = query.value.trim().toLowerCase()
  const src = props.payload?.sections || []
  if (!q) return src

  return src
    .map((sec) => ({
      ...sec,
      items: sec.items.filter(
        (item) =>
          item.label?.toLowerCase().includes(q) ||
          item.key?.toLowerCase().includes(q),
      ),
    }))
    .filter((sec) => sec.items.length)
})

const visibleCount = computed(() =>
  sections.value.reduce((n, sec) => n + sec.items.length, 0),
)

function cell(item, periodValue) {
  return item.values?.[periodValue]
}

function formatCell(item, value, period) {
  if (item?.isRatio) {
    return formatRatio(item.key, value, item.unit, {
      applicable: item.applicability?.[period] ?? item.applicable,
    })
  }
  return formatMoney(value, { isEps: item?.isEps })
}

function prevPeriodValue(periodValue) {
  const idx = periods.value.findIndex((p) => p.value === periodValue)
  if (idx < 0 || idx >= periods.value.length - 1) return undefined
  return periods.value[idx + 1]?.value
}

function delta(item, periodValue) {
  const prevValue = prevPeriodValue(periodValue)
  if (prevValue == null) return null
  return changePct(cell(item, periodValue), cell(item, prevValue))
}

function formatDelta(item, periodValue) {
  const d = delta(item, periodValue)
  if (d == null) return null
  return `${d > 0 ? '+' : ''}${d.toFixed(1)}%`
}

function updateScrollHints() {
  const el = scrollerRef.value
  if (!el) {
    scrollCanLeft.value = false
    scrollCanRight.value = false
    return
  }
  const maxScroll = el.scrollWidth - el.clientWidth
  scrollCanLeft.value = el.scrollLeft > 4
  scrollCanRight.value = maxScroll - el.scrollLeft > 4
}

function scrollByColumn(direction) {
  const el = scrollerRef.value
  if (!el) return
  el.scrollBy({ left: direction * Math.min(el.clientWidth * 0.72, 280), behavior: 'smooth' })
}

function syncMobile() {
  isMobile.value = window.matchMedia('(max-width: 767px)').matches
  updateScrollHints()
}

watch(
  () => [props.payload, props.loading, periodCount.value],
  async () => {
    await nextTick()
    updateScrollHints()
  },
)

watch(scrollerRef, (el, _, onCleanup) => {
  if (!el) return
  updateScrollHints()
  const observer = new ResizeObserver(() => updateScrollHints())
  observer.observe(el)
  onCleanup(() => observer.disconnect())
}, { flush: 'post' })

onMounted(() => {
  syncMobile()
  window.addEventListener('resize', syncMobile, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('resize', syncMobile)
})
</script>

<template>
  <div class="table-shell">
    <div v-if="payload && !loading" class="toolbar">
      <div class="counts muted">
        <span v-if="shownFields != null && totalFields != null">
          顯示 {{ query ? visibleCount : shownFields }} / {{ totalFields }} 科目
        </span>
        <span v-else-if="visibleCount">共 {{ visibleCount }} 科目</span>
      </div>
      <div class="toolbar-actions">
        <input
          v-model="query"
          class="search"
          type="search"
          placeholder="搜尋科目名稱或代碼…"
          aria-label="搜尋科目"
        />
        <label class="toggle-full">
          <input
            type="checkbox"
            :checked="showAllFields"
            @change="emit('toggle-full', ($event.target).checked)"
          />
          顯示全部科目
        </label>
      </div>
    </div>

    <div v-if="loading" class="state muted">讀取報表中…</div>
    <div v-else-if="!payload || !sections.length" class="state muted">
      {{ query ? '找不到符合的科目' : '尚無此報表資料' }}
    </div>
    <template v-else>
      <div v-if="periodCount" class="period-bar">
        <span class="period-badge mono">共 {{ periodCount }} 期</span>
        <span v-if="showPeriodNav" class="period-hint muted">
          <template v-if="scrollCanRight">左右滑動看全部 {{ periodCount }} 期</template>
          <template v-else-if="scrollCanLeft">已到最早季度 · 點 ‹ 回較新</template>
          <template v-else>全部 {{ periodCount }} 期</template>
        </span>
        <div v-if="showPeriodNav" class="period-nav" aria-label="季度捲動">
          <button
            type="button"
            class="period-nav-btn"
            :disabled="!scrollCanLeft"
            aria-label="較新季度"
            @click="scrollByColumn(-1)"
          >
            ‹
          </button>
          <button
            type="button"
            class="period-nav-btn"
            :disabled="!scrollCanRight"
            aria-label="較舊季度"
            @click="scrollByColumn(1)"
          >
            ›
          </button>
        </div>
      </div>
      <div class="scroller-wrap">
        <div
          v-if="scrollCanLeft"
          class="scroll-fade scroll-fade--left"
          aria-hidden="true"
        />
        <div
          v-if="scrollCanRight"
          class="scroll-fade scroll-fade--right"
          aria-hidden="true"
        />
        <div
          ref="scrollerRef"
          class="scroller"
          @scroll="updateScrollHints"
        >
      <table>
        <thead>
          <tr>
            <th class="sticky col-item">科目</th>
            <th
              v-for="p in periods"
              :key="p.value"
              class="col-num mono"
            >
              {{ p.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="sec in sections" :key="sec.id">
            <tr class="section-row">
              <td class="sticky col-item section-title">{{ sec.section }}</td>
              <td
                v-for="p in periods"
                :key="`${sec.id}-${p.value}`"
                class="section-fill"
              />
            </tr>
            <tr
              v-for="item in sec.items"
              :key="item.key"
              :class="{ emphasis: item.emphasis }"
            >
              <td class="sticky col-item">
                <span class="label">{{ item.label }}</span>
              </td>
              <td
                v-for="p in periods"
                :key="p.value"
                class="col-num mono"
                :class="changeClass(cell(item, p.value), cell(item, prevPeriodValue(p.value)))"
              >
                <div class="val">{{ formatCell(item, cell(item, p.value), p.value) }}</div>
                <div v-if="formatDelta(item, p.value)" class="delta">
                  {{ formatDelta(item, p.value) }}
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.table-shell {
  border: 1px solid var(--line);
  background: rgba(10, 12, 18, 0.55);
  min-height: 280px;
  min-width: 0;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 0.9rem;
  border-bottom: 1px solid rgba(232, 228, 220, 0.06);
}

.counts {
  font-size: 0.82rem;
  font-family: var(--mono);
  letter-spacing: 0.04em;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.search {
  min-width: min(280px, 100%);
  padding: 0.45rem 0.65rem;
  border: 1px solid var(--line);
  background: rgba(8, 10, 14, 0.85);
  color: var(--paper);
  font-size: 0.88rem;
}

.search:focus {
  outline: none;
  border-color: rgba(45, 212, 191, 0.45);
}

.toggle-full {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  color: var(--muted);
  cursor: pointer;
  white-space: nowrap;
}

.state {
  padding: 2.5rem 1.25rem;
  text-align: center;
}

.period-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  padding: 0.55rem 0.9rem;
  border-bottom: 1px solid rgba(232, 228, 220, 0.06);
  background: rgba(45, 212, 191, 0.04);
}

.period-badge {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  padding: 0.15rem 0.5rem;
  border: 1px solid rgba(45, 212, 191, 0.28);
  color: var(--aqua);
  background: rgba(45, 212, 191, 0.08);
}

.period-hint {
  flex: 1;
  min-width: 0;
  font-size: 0.76rem;
  letter-spacing: 0.04em;
}

.period-nav {
  display: none;
  gap: 0.35rem;
  margin-left: auto;
}

.period-nav-btn {
  min-width: 36px;
  min-height: 36px;
  padding: 0;
  border: 1px solid rgba(45, 212, 191, 0.35);
  background: rgba(8, 10, 14, 0.85);
  color: var(--aqua);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
}

.period-nav-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.scroller-wrap {
  position: relative;
  min-width: 0;
}

.scroll-fade {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 28px;
  pointer-events: none;
  z-index: 4;
}

.scroll-fade--left {
  left: 0;
  background: linear-gradient(90deg, rgba(10, 12, 18, 0.95), transparent);
}

.scroll-fade--right {
  right: 0;
  background: linear-gradient(270deg, rgba(10, 12, 18, 0.95), transparent);
}

.scroller {
  overflow-x: auto;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-x: contain;
  touch-action: pan-x pan-y;
  max-height: min(70vh, 720px);
  width: 100%;
  max-width: 100%;
}

table {
  width: max-content;
  min-width: max-content;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: auto;
}

th, td {
  padding: 0.7rem 0.9rem;
  border-bottom: 1px solid rgba(232, 228, 220, 0.06);
  vertical-align: top;
  white-space: nowrap;
}

thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #10151f;
  color: var(--muted);
  font-weight: 500;
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--line-strong);
}

.col-item {
  text-align: left;
  min-width: 180px;
  max-width: 220px;
  white-space: normal;
  overflow: hidden;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.35;
}

.sticky {
  position: -webkit-sticky;
  position: sticky;
  left: 0;
  z-index: 2;
  background: #0c1018;
  box-shadow: 1px 0 0 rgba(232, 228, 220, 0.08);
}

thead .sticky {
  z-index: 3;
  background: #10151f;
}

.col-num {
  text-align: right;
  min-width: 118px;
}

.section-row td {
  padding-top: 1rem;
  border-bottom-color: rgba(45, 212, 191, 0.18);
}

.section-row .section-title {
  color: var(--aqua);
  font-family: var(--display);
  font-size: 0.85rem;
  letter-spacing: 0.12em;
  background: #101820;
}

.section-row .section-fill {
  background: linear-gradient(90deg, rgba(45, 212, 191, 0.1), transparent 70%);
}

.emphasis .label {
  color: var(--paper);
  font-weight: 600;
}

.emphasis .val {
  color: var(--brass);
  font-weight: 600;
}

.label {
  display: block;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.val { font-size: 0.92rem; }

.delta {
  font-size: 0.68rem;
  opacity: 0.8;
  margin-top: 0.1rem;
}

.up .delta { color: var(--up); }
.down .delta { color: var(--down); }

@media (max-width: 767px) {
  .toolbar {
    padding: 0.7rem 0.75rem;
  }

  .toolbar-actions {
    width: 100%;
  }

  .search {
    width: 100%;
    min-width: 0;
    min-height: 44px;
    font-size: 1rem;
  }

  .toggle-full {
    min-height: 40px;
  }

  .period-bar {
    padding: 0.55rem 0.75rem;
  }

  .period-nav {
    display: inline-flex;
  }

  .scroll-fade--left {
    width: 18px;
  }

  .scroll-fade--right {
    width: 32px;
  }

  .scroller {
    max-height: min(60vh, 560px);
    overflow-x: scroll;
  }

  table {
    width: max-content;
    min-width: max-content;
  }

  .col-item {
    width: 128px;
    min-width: 128px;
    max-width: 128px;
    font-size: 0.78rem;
  }

  .col-num {
    width: 86px;
    min-width: 86px;
    max-width: 86px;
  }

  th, td {
    padding: 0.55rem 0.4rem;
  }

  .val {
    font-size: 0.82rem;
  }
}
</style>
