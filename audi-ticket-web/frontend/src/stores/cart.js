import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from './api'

export const useCartStore = defineStore('cart', () => {
    const carts = ref([])
    const loading = ref(false)
    const error = ref(null)

    async function fetchCarts() {
        loading.value = true
        try {
            // Assuming the API returns a list of carts
            const response = await api.get('/api/carts')
            // If response is just the array directly (based on old Carts.vue: carts.value = await api.get...)
            carts.value = Array.isArray(response) ? response : (response.carts || [])
        } catch (e) {
            console.error(e)
            error.value = "Failed to load carts"
        } finally {
            loading.value = false
        }
    }

    // Force update trigger (reactive counter)
    const _tick = ref(0)
    function triggerUpdate() {
        _tick.value++
    }

    // Backend stores UTC timestamps without Z suffix — append it for correct parsing
    const parseUtc = (dateStr) => {
        if (!dateStr) return new Date(0)
        return new Date(typeof dateStr === 'string' && !dateStr.endsWith('Z') ? dateStr + 'Z' : dateStr)
    }

    const validCarts = computed(() => {
        _tick.value
        const now = new Date()
        return carts.value.filter(c => {
            return parseUtc(c.expires_at) > now
        }).map(c => ({
            ...c,
            expires_at: parseUtc(c.expires_at)
        })).sort((a, b) => a.expires_at - b.expires_at)
    })

    return {
        carts,
        loading,
        error,
        fetchCarts,
        triggerUpdate,
        validCarts
    }
})
