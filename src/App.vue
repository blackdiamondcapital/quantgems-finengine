<script setup>
import { onMounted, ref } from 'vue'
import { api } from './api'
import LandingHero from './components/LandingHero.vue'
import EngineWorkspace from './components/EngineWorkspace.vue'
import ScreenerWorkspace from './components/ScreenerWorkspace.vue'

const view = ref('engine')
const stats = ref(null)
const ready = ref(false)
const seedCode = ref('2330')

onMounted(async () => {
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

function openStock(code) {
  seedCode.value = code || '2330'
  view.value = 'engine'
}
</script>

<template>
  <LandingHero
    v-if="view === 'landing'"
    :stats="stats"
    :ready="ready"
    @enter="enter"
  />
  <ScreenerWorkspace
    v-else-if="view === 'screener'"
    @back="view = 'landing'"
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
