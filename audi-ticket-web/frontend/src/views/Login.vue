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
.login-wrapper { height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg-color); }
.login-card { width: 100%; max-width: 400px; background: var(--card-bg); padding: 3rem; border-radius: 20px; box-shadow: 0 10px 40px var(--card-shadow); }

.login-header { text-align: center; margin-bottom: 2.5rem; }
.login-header h1 { font-size: 1.8rem; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 0.5rem; }
.login-header p { color: var(--text-secondary); }

.input-group { margin-bottom: 1.5rem; }
.input-group label { display: block; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.5rem; color: var(--text-primary); }
.input-group input { width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 10px; font-size: 1rem; transition: 0.2s; background: var(--input-bg); color: var(--text-primary); }
.input-group input:focus { border-color: var(--accent-blue); outline: none; background: var(--card-bg); color: var(--text-primary); }
.input-group input::placeholder { color: var(--text-tertiary); }

.submit-btn { width: 100%; padding: 14px; background: var(--btn-primary-bg); color: var(--btn-primary-text); border: none; border-radius: 12px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: 0.2s; margin-top: 1rem; }
.submit-btn:hover { background: var(--btn-primary-hover); transform: translateY(-1px); }
.submit-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.error-msg { color: var(--danger); font-size: 0.9rem; text-align: center; margin-bottom: 1rem; background: rgba(255, 59, 48, 0.1); padding: 10px; border-radius: 8px; }

@media (max-width: 768px) {
  .login-card { padding: 1.5rem; margin: 0 1rem; }
}
</style>
