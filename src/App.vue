<script setup>
import { defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from './api'
import { useAuth } from './lib/auth'
import { pagePath, resolveViewFromLocation, updatePageSeo } from './lib/seo'
import LandingHero from './components/LandingHero.vue'
import PwaInstallPrompt from './components/PwaInstallPrompt.vue'

const EngineWorkspace = defineAsyncComponent(() => import('./components/EngineWorkspace.vue'))
const ScreenerWorkspace = defineAsyncComponent(() => import('./components/ScreenerWorkspace.vue'))

const {
  isAuthenticated,
  user,
  setToken,
  fetchCurrentUser,
  consumeOAuthCallbackFromUrl,
} = useAuth()

const initialView = resolveViewFromLocation()
if (typeof window !== 'undefined') {
  const legacyParams = new URLSearchParams(window.location.search)
  if (legacyParams.has('view')) {
    legacyParams.delete('view')
    const query = legacyParams.toString()
    window.history.replaceState(null, '', `${pagePath(initialView)}${query ? `?${query}` : ''}`)
  }
}

const view = ref(initialView)
const stats = ref(null)
const ready = ref(false)
const seedCode = ref((() => {
  try {
    const raw = new URLSearchParams(window.location.search).get('symbol') || ''
    return raw.trim().toUpperCase().replace(/\.(TW|TWO)$/i, '') || '2330'
  } catch {
    return '2330'
  }
})())
const authStatus = ref('')

watch(view, updatePageSeo, { immediate: true })

function handlePopState() {
  view.value = resolveViewFromLocation()
}

onMounted(async () => {
  window.addEventListener('popstate', handlePopState)

  const oauth = consumeOAuthCallbackFromUrl()
  if (oauth.error) {
    authStatus.value = `登入失敗：${oauth.error}`
  } else if (oauth.token) {
    setToken(oauth.token)
    const me = await fetchCurrentUser()
    authStatus.value = me.success ? '已用 Google 登入' : (me.error || '登入狀態同步失敗')
  } else if (isAuthenticated.value && !user.value) {
    await fetchCurrentUser()
  }

  try {
    const [s] = await Promise.all([api.stats(), api.health()])
    stats.value = s
    ready.value = true
  } catch {
    ready.value = true
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('popstate', handlePopState)
})

function navigate(nextView, { replace = false } = {}) {
  if (typeof window !== 'undefined') {
    const method = replace ? 'replaceState' : 'pushState'
    window.history[method](null, '', pagePath(nextView))
  }
  view.value = nextView
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function enter() {
  seedCode.value = '2330'
  navigate('engine')
}

function openScreener() {
  navigate('screener')
}

function openStock(code) {
  seedCode.value = code || '2330'
  navigate('engine')
}

function openEngine() {
  navigate('engine')
}

function openLanding() {
  navigate('landing')
}
</script>

<template>
  <PwaInstallPrompt />
  <p v-if="authStatus" class="auth-status muted">{{ authStatus }}</p>
  <LandingHero
    v-if="view === 'landing'"
    :stats="stats"
    :ready="ready"
    @enter="enter"
    @goto-screener="openScreener"
  />
  <ScreenerWorkspace
    v-else-if="view === 'screener'"
    @back="openEngine"
    @goto-engine="openEngine"
    @open-stock="openStock"
  />
  <EngineWorkspace
    v-else
    :key="seedCode"
    :seed-code="seedCode"
    @back="openLanding"
    @goto-screener="openScreener"
  />
</template>

<style scoped>
.auth-status {
  margin: 0;
  padding: 0.45rem 1.25rem;
  font-size: 0.82rem;
  border-bottom: 1px solid var(--line);
}

@media (max-width: 767px) {
  .auth-status {
    padding: 0.45rem 0.85rem;
    font-size: 0.78rem;
  }
}
</style>
