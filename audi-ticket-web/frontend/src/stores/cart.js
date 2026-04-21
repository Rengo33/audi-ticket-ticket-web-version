import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from './api'

// Backend stores UTC timestamps without Z suffix — append it for correct parsing
const parseUtc = (d) => {
  if (!d) return new Date(0)
  if (d instanceof Date) return d
  return new Date(typeof d === 'string' && !d.endsWith('Z') ? d + 'Z' : d)
}

export const useCartStore = defineStore('cart', () => {
  const carts = ref([])
  const loading = ref(false)
  const error = ref(null)

  // Ticks every second for timer labels — kept separate from carts so cart
  // identity stays stable between ticks and cards don't re-render.
  const tick = ref(0)
  function triggerUpdate() { tick.value++ }

  async function fetchCarts() {
    loading.value = true
    try {
      const response = await api.get('/api/carts')
      const list = Array.isArray(response) ? response : (response.carts || [])
      carts.value = list.map(c => ({ ...c, expires_at: parseUtc(c.expires_at) }))
    } catch (e) {
      console.error(e)
      error.value = 'Failed to load carts'
    } finally {
      loading.value = false
    }
  }

  // Depends only on `carts` + `tick` (to drop expired entries as time advances).
  // `tick` only invalidates the list when an entry actually expires — the filter
  // result is reference-stable otherwise.
  const validCarts = computed(() => {
    tick.value
    const now = Date.now()
    return carts.value
      .filter(c => c.expires_at.getTime() > now)
      .sort((a, b) => a.expires_at - b.expires_at)
  })

  return { carts, loading, error, tick, fetchCarts, triggerUpdate, validCarts }
})
