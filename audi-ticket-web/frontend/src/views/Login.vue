<template>
  <div class="login">
    <!-- decorative scoreboard stripe -->
    <div class="scoreboard" aria-hidden="true">
      <div class="sb-row">
        <span class="sb-label mono">HOME</span>
        <span class="sb-team">FCB</span>
        <span class="sb-score mono">—</span>
      </div>
      <div class="sb-row sb-row-sep">
        <span class="sb-label mono">AWAY</span>
        <span class="sb-team">···</span>
        <span class="sb-score mono">—</span>
      </div>
      <div class="sb-kick mono">KICKOFF · 07:00 LOCAL</div>
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
        Sign in to monitor ticket drops, auto-cart on release,<br class="hide-mobile">
        and hand off to Auto-Checkout.
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
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const password = ref('')
const pwField = ref(null)

async function handleLogin() {
  if (!password.value || authStore.loading) return
  const success = await authStore.login(password.value)
  if (success) router.push('/')
  else await nextTick(() => pwField.value?.focus())
}

onMounted(async () => {
  await nextTick()
  pwField.value?.focus()
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
.hide-mobile { display: none; }
@media (min-width: 500px) { .hide-mobile { display: inline; } }

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

/* Scoreboard decoration — hidden on narrow screens, decorative on wide */
.scoreboard {
  display: none;
  position: absolute;
  bottom: 2.5rem; right: 2.5rem;
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

@media (min-width: 900px) {
  .login-panel { max-width: 520px; padding: 3rem 4rem; margin: 0; align-self: center; }
  .scoreboard { display: block; }
}

@media (min-width: 1200px) {
  .login-panel { margin-left: 10vw; }
}
</style>
