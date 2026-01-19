import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from './api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('auth_token') || null)
  const loading = ref(false)
  const error = ref(null)
  
  const isLoggedIn = computed(() => !!token.value)
  
  async function login(password) {
    loading.value = true
    error.value = null
    
    try {
      const response = await api.post('/api/auth/login', { password })
      
      if (response.success) {
        token.value = response.token
        localStorage.setItem('auth_token', response.token)
        return true
      } else {
        error.value = response.message
        return false
      }
    } catch (e) {
      error.value = 'Verbindungsfehler'
      return false
    } finally {
      loading.value = false
    }
  }
  
  async function logout() {
    try {
      await api.post('/api/auth/logout')
    } catch (e) {
      // Ignore errors
    }
    
    token.value = null
    localStorage.removeItem('auth_token')
  }
  
  function checkAuth() {
    // Token exists, assume logged in
    // Could add a /api/auth/verify endpoint
  }
  
  return {
    token,
    loading,
    error,
    isLoggedIn,
    login,
    logout,
    checkAuth
  }
})
