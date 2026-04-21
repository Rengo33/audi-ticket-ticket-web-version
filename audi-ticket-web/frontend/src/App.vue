<template>
  <div class="app" :data-auth="authStore.token ? 'in' : 'out'">
    <!-- Top rail: brand + status + theme -->
    <header v-if="authStore.token" class="rail">
      <div class="rail-inner">
        <div class="brand">
          <div class="brand-mark"><span class="brand-glyph">A</span></div>
          <div class="brand-text">
            <span class="brand-title">Audi Ticket Ops</span>
            <span class="brand-sub mono">{{ currentRouteName }}</span>
          </div>
        </div>

        <div class="rail-right">
          <div class="ws-chip" :class="{ 'is-off': !wsConnected }">
            <span class="live-dot"></span>
            <span class="mono">{{ wsConnected ? 'LIVE' : 'RECONNECT' }}</span>
          </div>
          <button @click="toggleTheme" class="rail-btn" :aria-label="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'">
            <svg v-if="theme === 'dark'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          </button>
          <button @click="logout" class="rail-btn logout-btn" aria-label="Sign out">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          </button>
        </div>
      </div>
    </header>

    <!-- Main view -->
    <main class="stage" :class="{ 'stage-auth': !authStore.token }">
      <div class="stage-inner">
        <router-view />
      </div>
    </main>

    <!-- Bottom dock nav (mobile) + side nav (desktop) -->
    <nav v-if="authStore.token" class="dock">
      <div class="dock-inner">
        <router-link v-for="item in navItems" :key="item.to" :to="item.to" class="dock-link">
          <span class="dock-icon" v-html="item.icon"></span>
          <span class="dock-label">{{ item.label }}</span>
        </router-link>
      </div>
    </nav>
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
const applyTheme = (t) => { document.documentElement.setAttribute('data-theme', t); localStorage.setItem('theme', t); };
const toggleTheme = () => { theme.value = theme.value === 'dark' ? 'light' : 'dark'; applyTheme(theme.value); };

const currentRouteName = computed(() => (route.name || 'Tasks').toString().toUpperCase());

const logout = () => { wsDisconnect(); authStore.logout(); router.push('/login'); };
const tokenGetter = () => authStore.token;

const navItems = [
  { to: '/games',   label: 'Games',   icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6L5.6 18.4"/></svg>` },
  { to: '/',        label: 'Tasks',   icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10M7 13h10M7 17h6"/></svg>` },
  { to: '/carts',   label: 'Carts',   icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4h3l2.5 12h12"/><path d="M7.5 16h12L22 7H6"/><circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/></svg>` },
  { to: '/billing', label: 'Billing', icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="5.5" width="19" height="13" rx="2"/><path d="M2.5 10h19M6 15h3M12 15h2"/></svg>` },
  { to: '/logs',    label: 'Logs',    icon: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16M4 10h16M4 15h10M4 20h16"/></svg>` },
];

watch(() => authStore.token, (token) => {
  if (token) wsConnect(token, tokenGetter);
  else wsDisconnect();
});

onMounted(() => {
  applyTheme(theme.value);
  authStore.checkAuth();
  if (authStore.token) { taskStore.fetchTasks(); wsConnect(authStore.token, tokenGetter); }
});

onUnmounted(() => { wsDisconnect(); });
</script>

<style>
/* ────────────────────────────────────────────────────────────
   App shell layout
   Desktop: top rail + left sidebar (via .dock md)
   Mobile:  top rail + bottom dock
   ──────────────────────────────────────────────────────────── */

.app {
  min-height: 100vh;
  min-height: 100dvh;
  display: grid;
  grid-template-rows: auto 1fr auto;
}
.app[data-auth="out"] {
  grid-template-rows: 1fr;
}

/* TOP RAIL */
.rail {
  position: sticky; top: 0; z-index: 40;
  background: color-mix(in oklab, var(--bg) 88%, transparent);
  backdrop-filter: saturate(160%) blur(14px);
  -webkit-backdrop-filter: saturate(160%) blur(14px);
  border-bottom: 1px solid var(--line);
  padding-top: var(--safe-t);
}
.rail-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 10px 16px;
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px;
}
.brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
.brand-mark {
  width: 38px; height: 38px;
  border-radius: 6px;
  background: var(--signal);
  color: var(--signal-ink);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800;
  flex-shrink: 0;
  position: relative;
}
.brand-mark::after {
  content: "";
  position: absolute;
  top: 4px; right: 4px;
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--signal-ink);
  opacity: 0.9;
}
.brand-glyph {
  font-family: var(--font-sans);
  font-size: 1.1rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  line-height: 1;
}

.brand-text { display: flex; flex-direction: column; line-height: 1.1; min-width: 0; }
.brand-title {
  font-size: 0.9375rem; font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.brand-sub {
  font-size: 0.6875rem; font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--ink-4);
  margin-top: 2px;
}

.rail-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.ws-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--ok);
  background: var(--ok-soft);
}
.ws-chip.is-off { color: var(--bad); background: var(--bad-soft); }

.rail-btn {
  width: 36px; height: 36px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-2);
  display: inline-flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  -webkit-tap-highlight-color: transparent;
}
.rail-btn:hover { background: var(--surface-hover); color: var(--ink); }

/* STAGE (main content) */
.stage { min-height: 0; }
.stage-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 1.25rem 1rem 1.5rem;
}
.stage-auth .stage-inner { padding: 0; max-width: 100%; }

/* DOCK (nav) — bottom on mobile, side on desktop */
.dock {
  position: sticky; bottom: 0; z-index: 40;
  padding-bottom: var(--safe-b);
  background: color-mix(in oklab, var(--bg) 88%, transparent);
  backdrop-filter: saturate(160%) blur(14px);
  -webkit-backdrop-filter: saturate(160%) blur(14px);
  border-top: 1px solid var(--line);
}
.dock-inner {
  max-width: 640px;
  margin: 0 auto;
  padding: 6px;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 2px;
}
.dock-link {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 3px;
  padding: 8px 4px;
  text-decoration: none;
  color: var(--ink-3);
  border-radius: 10px;
  transition: color 0.15s, background 0.15s;
  min-height: 52px;
  -webkit-tap-highlight-color: transparent;
  position: relative;
}
.dock-link:hover { color: var(--ink); }
.dock-link.router-link-exact-active {
  color: var(--ink);
}
.dock-link.router-link-exact-active::before {
  content: "";
  position: absolute; top: 0; left: 50%;
  width: 28px; height: 2px;
  background: var(--signal);
  transform: translateX(-50%);
  border-radius: 0 0 2px 2px;
}
.dock-icon { display: inline-flex; }
.dock-icon svg { width: 22px; height: 22px; }
.dock-label {
  font-family: var(--font-mono);
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

/* Desktop: switch to sidebar */
@media (min-width: 900px) {
  .app { grid-template-columns: 220px 1fr; grid-template-rows: auto 1fr; }
  .app[data-auth="in"] { grid-template-areas: "rail rail" "dock stage"; }
  .app[data-auth="out"] { grid-template-columns: 1fr; grid-template-rows: 1fr; }
  .rail { grid-area: rail; }
  .stage { grid-area: stage; }
  .dock {
    grid-area: dock;
    position: sticky;
    top: 57px; /* sits under rail */
    align-self: start;
    height: calc(100dvh - 57px - var(--safe-b));
    border-top: none;
    border-right: 1px solid var(--line);
    padding: 12px 12px calc(12px + var(--safe-b));
    background: var(--bg);
  }
  .dock-inner {
    display: flex; flex-direction: column;
    grid-template-columns: none;
    gap: 2px;
    max-width: none;
    padding: 0;
  }
  .dock-link {
    flex-direction: row;
    justify-content: flex-start;
    gap: 12px;
    padding: 10px 12px;
    min-height: 44px;
    border-radius: 8px;
  }
  .dock-link.router-link-exact-active {
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--line);
    padding: 9px 11px;
  }
  .dock-link.router-link-exact-active::before {
    top: 50%;
    left: -12px;
    width: 3px;
    height: 20px;
    transform: translateY(-50%);
    border-radius: 0 2px 2px 0;
  }
  .dock-icon svg { width: 18px; height: 18px; }
  .dock-label { font-size: 0.8125rem; letter-spacing: 0.02em; text-transform: none; font-family: var(--font-sans); font-weight: 600; }

  .stage-inner { padding: 1.5rem 2rem 2.5rem; }
}

/* Tighten rail on tiny screens */
@media (max-width: 400px) {
  .ws-chip { padding: 5px 8px; }
  .brand-text { display: none; }
  .brand-mark { width: 32px; height: 32px; }
}
</style>
