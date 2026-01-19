<template>
    <div class="login-wrapper">
        <div class="login-card">
            <div class="login-header">
                <h1>AudiTicket</h1>
                <p>Welcome back</p>
            </div>
            
            <form @submit.prevent="handleLogin" class="login-form">
                <div class="input-group">
                    <label>Password</label>
                    <input type="password" v-model="password" required placeholder="Enter password" :disabled="authStore.loading">
                </div>
                
                <div v-if="authStore.error" class="error-msg">{{ authStore.error }}</div>
                
                <button type="submit" :disabled="authStore.loading || !password" class="submit-btn">
                    {{ authStore.loading ? 'Signing in...' : 'Sign In' }}
                </button>
            </form>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const password = ref('')

async function handleLogin() {
  const success = await authStore.login(password.value)
  if (success) {
    router.push('/')
  }
}
</script>

<style scoped>
.login-wrapper { height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f5f7; }
.login-card { width: 100%; max-width: 400px; background: white; padding: 3rem; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.05); }

.login-header { text-align: center; margin-bottom: 2.5rem; }
.login-header h1 { font-size: 1.8rem; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 0.5rem; }
.login-header p { color: #6c6c70; }

.input-group { margin-bottom: 1.5rem; }
.input-group label { display: block; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.5rem; color: #1c1c1e; }
.input-group input { width: 100%; padding: 12px; border: 1px solid #d1d1d6; border-radius: 10px; font-size: 1rem; transition: 0.2s; background: #f9f9f9; color: #1c1c1e; }
.input-group input:focus { border-color: #000; outline: none; background: white; color: #1c1c1e; }
.input-group input::placeholder { color: #8e8e93; }

.submit-btn { width: 100%; padding: 14px; background: #000; color: white; border: none; border-radius: 12px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: 0.2s; margin-top: 1rem; }
.submit-btn:hover { background: #333; transform: translateY(-1px); }
.submit-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.error-msg { color: #ff3b30; font-size: 0.9rem; text-align: center; margin-bottom: 1rem; background: rgba(255, 59, 48, 0.1); padding: 10px; border-radius: 8px; }
</style>
