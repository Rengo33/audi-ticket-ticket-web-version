<template>
  <div class="app-container">
    <nav class="sidebar" v-if="authStore.token">
      <div class="brand">
        <h1>AudiTicket</h1>
      </div>
      
      <div class="nav-links">
        <router-link to="/games" class="nav-item">
          <span class="icon">⚽</span> Games
        </router-link>
        <router-link to="/" class="nav-item">
          <span class="icon">📋</span> Tasks
        </router-link>
        <router-link to="/carts" class="nav-item">
          <span class="icon">🛒</span> Carts
        </router-link>
      </div>

      <div class="user-profile">
        <button @click="logout" class="logout-btn">Sign Out</button>
      </div>
    </nav>

    <main class="content">
      <header class="top-bar" v-if="authStore.token">
        <h2>{{ currentRouteName }}</h2>
        <div class="status-indicator">
            <span class="dot"></span> Connected
        </div>
      </header>
      
      <div class="view-container">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from './stores/auth';
import { useTaskStore } from './stores/tasks';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const taskStore = useTaskStore();

const currentRouteName = computed(() => {
    if (route.name === 'Dashboard') return 'Tasks';
    return route.name || 'Dashboard';
});

const logout = () => {
    authStore.logout();
    router.push('/login');
};

onMounted(() => {
    authStore.checkAuth();
    if (authStore.token) {
        taskStore.fetchTasks();
    }
});
</script>

<style>
:root {
  --bg-color: #f5f5f7;
  --card-bg: #ffffff;
  --text-primary: #1c1c1e;
  --text-secondary: #6c6c70;
  --accent: #1c1c1e;
  --accent-blue: #007AFF;
  --border: #d1d1d6;
  --danger: #ff3b30;
  --success: #34c759;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif; background: var(--bg-color); color: var(--text-primary); -webkit-font-smoothing: antialiased; }

.app-container { display: flex; height: 100vh; overflow: hidden; }

/* Sidebar */
.sidebar { width: 260px; background: var(--card-bg); border-right: 1px solid var(--border); display: flex; flex-direction: column; padding: 2rem 1rem; }
.brand h1 { font-size: 1.2rem; font-weight: 700; margin-bottom: 2rem; padding-left: 1rem; letter-spacing: -0.5px; }

.nav-links { flex: 1; display: flex; flex-direction: column; gap: 0.5rem; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; text-decoration: none; color: var(--text-secondary); border-radius: 12px; transition: all 0.2s; font-weight: 500; }
.nav-item:hover { background: var(--bg-color); color: var(--text-primary); }
.nav-item.router-link-active { background: var(--accent); color: white; }
.nav-item .icon { font-size: 1.2rem; }

.user-profile { padding-top: 1rem; border-top: 1px solid var(--border); }
.logout-btn { width: 100%; padding: 10px; background: none; border: 1px solid var(--border); border-radius: 8px; cursor: pointer; font-weight: 600; color: var(--text-primary); transition: 0.2s; }
.logout-btn:hover { background: var(--bg-color); }

/* Main Content */
.content { flex: 1; display: flex; flex-direction: column; background: var(--bg-color); }
.top-bar { height: 70px; display: flex; align-items: center; justify-content: space-between; padding: 0 2rem; background: var(--bg-color); border-bottom: 1px solid var(--border); backdrop-filter: blur(20px); }
.top-bar h2 { font-size: 1.5rem; font-weight: 700; }

.status-indicator { font-size: 0.85rem; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); }

.view-container { flex: 1; overflow-y: auto; padding: 2rem; }
</style>
