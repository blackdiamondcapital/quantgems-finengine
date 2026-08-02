<script setup>
import { onMounted, ref } from 'vue'
import { api } from './api'
import { useAuth } from './lib/auth'
import LandingHero from './components/LandingHero.vue'
import EngineWorkspace from './components/EngineWorkspace.vue'
import ScreenerWorkspace from './components/ScreenerWorkspace.vue'
import PwaInstallPrompt from './components/PwaInstallPrompt.vue'

const {
  isAuthenticated,
  user,
  setToken,
  fetchCurrentUser,
  consumeOAuthCallbackFromUrl,
} = useAuth()

const view = ref('engine')
const stats = ref(null)
const ready = ref(false)
const seedCode = ref('2330')
const authStatus = ref('')

onMounted(async () => {
  try {
    const params = new URLSearchParams(window.location.search)
    if ((params.get('view') || '') === 'screener') {
      view.value = 'screener'
    }
  } catch {
    /* ignore */
  }

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

function enter() {
  seedCode.value = '2330'
  view.value = 'engine'
}

function openScreener() {
  view.value = 'screener'
}

function openStock(code) {
  seedCode.value = code || '2330'
  view.value = 'engine'
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
    @back="view = 'engine'"
    @goto-engine="view = 'engine'"
    @open-stock="openStock"
  />
  <EngineWorkspace
    v-else
    :key="seedCode"
    :seed-code="seedCode"
    @back="view = 'landing'"
    @goto-screener="view = 'screener'"
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
