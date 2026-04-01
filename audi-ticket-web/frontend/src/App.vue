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
        <button @click="toggleTheme" class="theme-toggle-btn">
          {{ theme === 'dark' ? '☀️' : '🌙' }}
        </button>
        <button @click="logout" class="logout-btn">Sign Out</button>
      </div>
    </nav>

    <main class="content">
      <header class="top-bar" v-if="authStore.token">
        <h2>{{ currentRouteName }}</h2>
        <div class="top-bar-right">
          <button @click="toggleTheme" class="theme-toggle-mobile">
            {{ theme === 'dark' ? '☀️' : '🌙' }}
          </button>
          <div class="status-indicator" :class="{ disconnected: !wsConnected }">
              <span class="dot" :class="{ offline: !wsConnected }"></span>
              {{ wsConnected ? 'Connected' : 'Reconnecting...' }}
          </div>
        </div>
      </header>

      <div class="view-container">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from './stores/auth';
import { useTaskStore } from './stores/tasks';
import { useWebSocket } from './stores/websocket';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const taskStore = useTaskStore();
const { connected: wsConnected, connect: wsConnect, disconnect: wsDisconnect } = useWebSocket();

const theme = ref(localStorage.getItem('theme') || 'light');

const applyTheme = (t) => {
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('theme', t);
};

const toggleTheme = () => {
    theme.value = theme.value === 'dark' ? 'light' : 'dark';
    applyTheme(theme.value);
};

const currentRouteName = computed(() => {
    if (route.name === 'Dashboard') return 'Tasks';
    return route.name || 'Dashboard';
});

const logout = () => {
    wsDisconnect();
    authStore.logout();
    router.push('/login');
};

const tokenGetter = () => authStore.token;

// Connect WebSocket when token is available
watch(() => authStore.token, (token) => {
    if (token) {
        wsConnect(token, tokenGetter);
    } else {
        wsDisconnect();
    }
});

onMounted(() => {
    applyTheme(theme.value);
    authStore.checkAuth();
    if (authStore.token) {
        taskStore.fetchTasks();
        wsConnect(authStore.token, tokenGetter);
    }
});

onUnmounted(() => {
    wsDisconnect();
});
</script>

<style>
:root {
  --bg-color: #f5f5f7;
  --card-bg: #ffffff;
  --text-primary: #1c1c1e;
  --text-secondary: #6c6c70;
  --text-tertiary: #8e8e93;
  --accent: #1c1c1e;
  --accent-blue: #007AFF;
  --border: #d1d1d6;
  --border-light: #e5e5ea;
  --danger: #ff3b30;
  --success: #34c759;
  --warning: #ff9500;
  --purple: #5856d6;
  --stat-bg: #f9f9fb;
  --input-bg: #f9f9f9;
  --hover-bg: #f2f2f7;
  --btn-primary-bg: #1c1c1e;
  --btn-primary-text: white;
  --btn-primary-hover: #3a3a3c;
  --modal-overlay: rgba(0, 0, 0, 0.5);
  --card-shadow: rgba(0, 0, 0, 0.08);
  --card-image-gradient-start: #1c1c1e;
  --card-image-gradient-end: #3a3a3c;
  --nav-glass-bg: rgba(255, 255, 255, 0.65);
  --nav-item-bg: rgba(0, 0, 0, 0.04);
  --nav-item-hover: rgba(0, 0, 0, 0.08);
  --nav-active-bg: rgba(0, 122, 255, 0.15);
  --nav-active-shadow: rgba(0, 122, 255, 0.2);
}

[data-theme="dark"] {
  --bg-color: #000000;
  --card-bg: #1c1c1e;
  --text-primary: #f5f5f7;
  --text-secondary: #a1a1a6;
  --text-tertiary: #8e8e93;
  --accent: #ffffff;
  --accent-blue: #0A84FF;
  --border: #38383a;
  --border-light: #2c2c2e;
  --danger: #ff453a;
  --success: #30d158;
  --warning: #ff9f0a;
  --purple: #5e5ce6;
  --stat-bg: #2c2c2e;
  --input-bg: #2c2c2e;
  --hover-bg: #2c2c2e;
  --btn-primary-bg: #ffffff;
  --btn-primary-text: #1c1c1e;
  --btn-primary-hover: #e5e5ea;
  --card-shadow: rgba(0, 0, 0, 0.3);
  --card-image-gradient-start: #2c2c2e;
  --card-image-gradient-end: #1c1c1e;
  --nav-glass-bg: rgba(28, 28, 30, 0.75);
  --nav-item-bg: rgba(255, 255, 255, 0.06);
  --nav-item-hover: rgba(255, 255, 255, 0.1);
  --nav-active-bg: rgba(10, 132, 255, 0.2);
  --nav-active-shadow: rgba(10, 132, 255, 0.3);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif; background: var(--bg-color); color: var(--text-primary); -webkit-font-smoothing: antialiased; }

.app-container { display: flex; height: 100vh; overflow: hidden; }

/* Sidebar */
.sidebar { width: 260px; background: var(--card-bg); border-right: 1px solid var(--border); display: flex; flex-direction: column; padding: 2rem 1rem; }
.brand h1 { font-size: 1.2rem; font-weight: 700; margin-bottom: 2rem; padding-left: 1rem; letter-spacing: -0.5px; }

.nav-links { flex: 1; display: flex; flex-direction: column; gap: 0.5rem; }
.nav-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; text-decoration: none; color: var(--text-secondary); border-radius: 12px; transition: all 0.2s; font-weight: 500; }
.nav-item:hover { background: var(--hover-bg); color: var(--text-primary); }
.nav-item.router-link-active { background: var(--accent); color: var(--btn-primary-text); }
.nav-item .icon { font-size: 1.2rem; }

.user-profile { padding-top: 1rem; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 0.5rem; }
.theme-toggle-btn { padding: 10px; background: var(--hover-bg); border: 1px solid var(--border); border-radius: 8px; cursor: pointer; font-size: 1.1rem; transition: 0.2s; }
.theme-toggle-btn:hover { background: var(--bg-color); }
.logout-btn { width: 100%; padding: 10px; background: none; border: 1px solid var(--border); border-radius: 8px; cursor: pointer; font-weight: 600; color: var(--text-primary); transition: 0.2s; }
.logout-btn:hover { background: var(--hover-bg); }

/* Main Content */
.content { flex: 1; display: flex; flex-direction: column; background: var(--bg-color); }
.top-bar { height: 70px; display: flex; align-items: center; justify-content: space-between; padding: 0 2rem; background: var(--bg-color); border-bottom: 1px solid var(--border); backdrop-filter: blur(20px); }
.top-bar h2 { font-size: 1.5rem; font-weight: 700; }
.top-bar-right { display: flex; align-items: center; gap: 12px; }

.theme-toggle-mobile { display: none; }

.status-indicator { font-size: 0.85rem; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; }
.status-indicator.disconnected { color: var(--danger); }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); }
.dot.offline { background: var(--danger); }

.view-container { flex: 1; overflow-y: auto; padding: 2rem; }

/* Mobile Responsive */
@media (max-width: 768px) {
  .app-container { flex-direction: column-reverse; }

  .sidebar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    width: 100%;
    height: auto;
    flex-direction: row;
    padding: 8px 12px;
    padding-bottom: calc(8px + env(safe-area-inset-bottom));
    border-right: none;
    border-top: none;
    z-index: 50;
    background: var(--nav-glass-bg);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    backdrop-filter: saturate(180%) blur(20px);
    box-shadow: 0 -1px 0 rgba(0, 0, 0, 0.08), 0 -8px 32px rgba(0, 0, 0, 0.06);
  }
  .brand { display: none; }
  .user-profile { display: none; }

  .theme-toggle-mobile {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background: var(--hover-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    cursor: pointer;
    font-size: 1rem;
  }

  .nav-links {
    flex-direction: row;
    justify-content: center;
    width: 100%;
    gap: 8px;
    align-items: center;
  }
  .nav-item {
    flex-direction: row;
    gap: 6px;
    padding: 10px 20px;
    font-size: 0.85rem;
    font-weight: 600;
    border-radius: 100px;
    background: var(--nav-item-bg);
    color: var(--text-secondary);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .nav-item:hover { background: var(--nav-item-hover); }
  .nav-item.router-link-active {
    background: var(--nav-active-bg);
    color: var(--accent-blue);
    box-shadow: 0 2px 12px var(--nav-active-shadow);
  }
  .nav-item .icon { font-size: 1.1rem; }

  .content { min-height: 0; }
  .top-bar { padding: 0 1rem; height: 56px; }
  .top-bar h2 { font-size: 1.2rem; }
  .view-container { padding: 1rem; padding-bottom: 70px; }
}
</style>
