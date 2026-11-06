<template>
  <div class="login">
    <!-- scoreboard: next fixture + the ones after it (public /api/games/upcoming) -->
    <div class="scoreboard" :class="{ empty: !nextGame }">
      <div class="sb-row">
        <span class="sb-label mono">HOME</span>
        <span class="sb-team">FCB</span>
        <span class="sb-score mono">—</span>
      </div>
      <div class="sb-row sb-row-sep">
        <span class="sb-label mono">AWAY</span>
        <span class="sb-team">{{ nextGame?.opponent || '···' }}</span>
        <span class="sb-score mono">—</span>
      </div>
      <div class="sb-kick mono">KICKOFF · {{ nextGame ? countdown : '—' }}</div>
      <div v-if="nextGame" class="sb-meta mono">
        <span>{{ fixtureDate(nextGame) }} · {{ nextGame.location.toUpperCase() }}</span>
        <span class="sb-status" :class="nextGame.status">{{ statusLabel(nextGame) }}</span>
      </div>
      <ul v-if="fixtures.length > 1" class="sb-fixtures">
        <li v-for="f in fixtures.slice(1)" :key="f.kickoff_utc">
          <span class="sb-fx-date mono">{{ fixtureDate(f) }}</span>
          <span class="sb-fx-team">{{ f.opponent }}</span>
          <span class="sb-status mono" :class="f.status">{{ statusLabel(f) }}</span>
        </li>
      </ul>
    </div>

    <div class="login-panel">
      <div class="login-crest">
        <div class="crest-mark">A</div>
        <div class="crest-label mono">AUDI TICKET OPS</div>
      </div>

      <h1 class="login-title">
        Matchday<br>
        <span class="login-title-red">command.</span>
      </h1>

      <p class="login-sub">
        Sign in to monitor ticket drops, auto-cart on release, and hand off to Auto-Checkout.
      </p>

      <form @submit.prevent="handleLogin" class="login-form" novalidate>
        <label class="field" for="login-pw">
          <span class="field-label">Passphrase</span>
          <input
            id="login-pw"
            ref="pwField"
            type="password"
            v-model="password"
            autocomplete="current-password"
            placeholder="Enter passphrase"
            :disabled="authStore.loading"
            @keydown.enter="handleLogin"
          >
        </label>

        <div v-if="authStore.error" class="login-error" role="alert">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
          {{ authStore.error }}
        </div>

        <button type="submit" :disabled="authStore.loading || !password" class="btn btn-primary login-btn">
          <span>{{ authStore.loading ? 'Authorising…' : 'Enter the pit lane' }}</span>
          <svg v-if="!authStore.loading" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </button>
      </form>

      <div class="login-foot mono">PRIVATE · INTERNAL USE · v1.0</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const password = ref('')
const pwField = ref(null)

const fixtures = ref([])
const nextGame = computed(() => fixtures.value[0] || null)
const countdown = ref('—')
let tickTimer = null
let fetchController = null

// `/` followed by a non-slash, non-backslash. Rejects `//evil.com`,
// `/\evil.com`, and any non-relative URL that could redirect off-origin.
const SAFE_REDIRECT = /^\/[^/\\]/

async function handleLogin() {
  if (!password.value || authStore.loading) return
  const success = await authStore.login(password.value)
  if (success) {
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.push(SAFE_REDIRECT.test(redirect) ? redirect : '/')
  } else {
    await nextTick(() => pwField.value?.focus())
  }
}

function formatCountdown(kickoffMs) {
  const diff = kickoffMs - Date.now()
  if (diff <= 0) return 'LIVE'
  const s = Math.floor(diff / 1000)
  const days = Math.floor(s / 86400)
  const hours = Math.floor((s % 86400) / 3600)
  const mins = Math.floor((s % 3600) / 60)
  const secs = s % 60
  const pad = n => String(n).padStart(2, '0')
  if (days > 0) return `${days}d ${hours}h ${pad(mins)}m ${pad(secs)}s`
  return `${pad(hours)}:${pad(mins)}:${pad(secs)}`
}

// match_date/match_time are Berlin local: "2026-11-20" + "20:30" -> "FRI 20.11 · 20:30"
function fixtureDate(f) {
  if (!f.match_date) return '—'
  const [y, m, d] = f.match_date.split('-')
  const wd = new Date(Date.UTC(+y, +m - 1, +d)).toLocaleDateString('en-GB', { weekday: 'short', timeZone: 'UTC' })
  return `${wd.toUpperCase()} ${d}.${m}${f.match_time ? ` · ${f.match_time}` : ''}`
}

function statusLabel(f) {
  if (f.status === 'on_sale') return 'ON SALE'
  if (f.status === 'sold_out') return 'SOLD OUT'
  if (f.sale_date) {
    const [, m, d] = f.sale_date.split('-')
    return `SALE ${d}.${m}`
  }
  return 'SOON'
}

async function loadNextGame() {
  fetchController = new AbortController()
  try {
    const res = await fetch('/api/games/upcoming', { signal: fetchController.signal })
    if (!res.ok) return
    const data = await res.json()
    if (!Array.isArray(data) || !data.length || !data[0].kickoff_utc) return
    fixtures.value = data
    const kickoffMs = new Date(data[0].kickoff_utc).getTime()
    countdown.value = formatCountdown(kickoffMs)
    if (tickTimer) clearInterval(tickTimer)
    tickTimer = setInterval(() => {
      const next = formatCountdown(kickoffMs)
      countdown.value = next
      // Stop ticking once the match is live — the value won't change anymore.
      if (next === 'LIVE') {
        clearInterval(tickTimer)
        tickTimer = null
      }
    }, 1000)
  } catch (e) {
    if (e.name !== 'AbortError') console.warn('Failed to load next game:', e)
  }
}

onMounted(async () => {
  await nextTick()
  pwField.value?.focus()
  loadNextGame()
})

onUnmounted(() => {
  if (tickTimer) clearInterval(tickTimer)
  if (fetchController) fetchController.abort()
})
</script>

<style scoped>
.login {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: 1fr;
  background: var(--bg);
  position: relative;
  overflow: hidden;
}

/* Big red diagonal signature in the corner */
.login::before {
  content: "";
  position: absolute;
  top: -40%; right: -30%;
  width: 80vw; height: 80vw;
  max-width: 900px; max-height: 900px;
  background: var(--signal);
  opacity: 0.06;
  transform: rotate(24deg);
  z-index: 0;
  pointer-events: none;
}
.login::after {
  content: "";
  position: absolute;
  bottom: 0; left: 0;
  width: 100%; height: 4px;
  background: var(--signal);
  z-index: 0;
}

.login-panel {
  padding: 2rem 1.5rem calc(2rem + var(--safe-b));
  padding-top: calc(2rem + var(--safe-t));
  display: flex; flex-direction: column;
  justify-content: center;
  max-width: 460px;
  width: 100%;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}

.login-crest {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 2rem;
}
.crest-mark {
  width: 44px; height: 44px;
  border-radius: 6px;
  background: var(--signal);
  color: var(--signal-ink);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.25rem; font-weight: 900;
  letter-spacing: -0.03em;
  line-height: 1;
  position: relative;
}
.crest-mark::after {
  content: "";
  position: absolute;
  top: 4px; right: 4px;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--signal-ink);
}
.crest-label {
  font-size: 0.6875rem; font-weight: 600;
  letter-spacing: 0.18em;
  color: var(--ink-3);
  line-height: 1;
}

.login-title {
  font-size: clamp(2.25rem, 9vw, 3.75rem);
  font-weight: 900;
  letter-spacing: -0.035em;
  line-height: 0.95;
  color: var(--ink);
  margin-bottom: 1rem;
}
.login-title-red { color: var(--signal); font-style: italic; }

.login-sub {
  font-size: 1rem;
  color: var(--ink-3);
  line-height: 1.5;
  margin-bottom: 2rem;
  max-width: 38ch;
}
.login-form { display: flex; flex-direction: column; gap: 1rem; }
.login-form .field { margin-bottom: 0; }
.login-btn {
  height: 52px;
  width: 100%;
  font-size: 0.9375rem;
  letter-spacing: 0.01em;
  margin-top: 4px;
  position: relative;
  overflow: hidden;
}
.login-btn::after {
  content: "";
  position: absolute;
  right: 0; top: 0; bottom: 0;
  width: 8px;
  background: rgba(0, 0, 0, 0.15);
}

.login-error {
  display: flex; align-items: center; gap: 8px;
  font-size: 0.8125rem; font-weight: 500;
  color: var(--bad);
  background: var(--bad-soft);
  border: 1px solid color-mix(in oklab, var(--bad) 40%, transparent);
  padding: 10px 12px;
  border-radius: var(--radius);
}

.login-foot {
  margin-top: 2.5rem;
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.22em;
  color: var(--ink-4);
}

/* Scoreboard — in the flow under the form on narrow screens (only once a
   fixture loaded), floating bottom-right on wide ones */
.scoreboard {
  order: 1;
  align-self: start;
  position: relative;
  width: calc(100% - 3rem);
  max-width: 412px;
  margin: 0 auto calc(2rem + var(--safe-b));
  z-index: 1;
  padding: 1rem 1.25rem;
  background: var(--ink);
  color: var(--bg);
  border-radius: 6px;
  min-width: 240px;
  box-shadow: 0 16px 48px -12px rgba(10, 10, 11, 0.25);
  border-left: 4px solid var(--signal);
}
.sb-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: baseline;
  gap: 10px;
  padding: 4px 0;
}
.sb-row-sep { border-top: 1px dashed rgba(255,255,255,0.15); padding-top: 8px; margin-top: 4px; }
.sb-label {
  font-size: 0.625rem;
  letter-spacing: 0.16em;
  color: var(--ink-4);
}
.sb-team {
  font-family: var(--font-sans);
  font-size: 1.25rem;
  font-weight: 900;
  letter-spacing: -0.02em;
  min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.sb-score {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--signal);
}
.sb-kick {
  font-size: 0.625rem;
  letter-spacing: 0.18em;
  color: var(--ink-3);
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.08);
  text-align: center;
}
.scoreboard.empty { display: none; }
.sb-meta {
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
  font-size: 0.625rem;
  letter-spacing: 0.14em;
  color: var(--ink-4);
  margin-top: 8px;
}
.sb-status { color: var(--signal); font-weight: 700; letter-spacing: 0.14em; font-size: 0.625rem; white-space: nowrap; }
.sb-status.on_sale { color: var(--ok); }
.sb-status.sold_out { color: var(--ink-4); }
.sb-fixtures {
  list-style: none;
  margin: 10px 0 0; padding: 8px 0 0;
  border-top: 1px solid rgba(255,255,255,0.08);
  display: flex; flex-direction: column; gap: 6px;
}
.sb-fixtures li {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: baseline;
  gap: 10px;
}
.sb-fx-date { font-size: 0.625rem; letter-spacing: 0.1em; color: var(--ink-4); white-space: nowrap; }
.sb-fx-team {
  font-size: 0.8125rem; font-weight: 700;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  min-width: 0;
}

@media (min-width: 900px) {
  .login-panel { max-width: 520px; padding: 3rem 4rem; margin: 0; align-self: center; }
  .scoreboard {
    position: absolute;
    bottom: 2.5rem; right: 2.5rem;
    width: auto; max-width: 340px;
    margin: 0;
  }
  .scoreboard.empty { display: block; }
}

@media (min-width: 1200px) {
  .login-panel { margin-left: 10vw; }
}
</style>
