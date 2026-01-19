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

    const validCarts = computed(() => {
        // dep on _tick
        _tick.value
        const now = new Date()
        return carts.value.filter(c => {
            const expiresAt = new Date(c.expires_at) // API likely returns ISO string
            return expiresAt > now
        }).map(c => ({
            ...c,
            // Calculate progress or remaining time here if needed, or do it in component
            expires_at: new Date(c.expires_at) // Ensure Date object
        })).sort((a, b) => a.expires_at - b.expires_at) // Expiring soonest first? Or latest? Let's say expiring soonest first.
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
