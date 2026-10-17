<template>
  <div v-if="show" class="push-banner" :class="{ 'is-ios': push.needsInstallFirst }">
    <div class="push-icon">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
        <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      </svg>
    </div>

    <div class="push-copy">
      <div class="push-title">
        <template v-if="push.needsInstallFirst">Add to Home Screen for notifications</template>
        <template v-else-if="push.permission === 'denied'">Notifications are blocked</template>
        <template v-else>Get pinged when a cart lands</template>
      </div>
      <div class="push-sub">
        <template v-if="push.needsInstallFirst">
          Tap share → <strong>Add to Home Screen</strong>, then open Audi Ops from the home screen.
        </template>
        <template v-else-if="push.permission === 'denied'">
          Enable notifications for this site in your browser settings, then reload.
        </template>
        <template v-else>
          Same signals as Discord — cart success, ACO step updates — straight to your phone.
        </template>
      </div>
      <div v-if="push.error" class="push-error mono">{{ push.error }}</div>
    </div>

    <div class="push-actions">
      <button
        v-if="!push.needsInstallFirst && push.permission !== 'denied'"
        @click="onEnable"
        :disabled="push.busy"
        class="btn btn-primary push-cta"
      >
        {{ push.busy ? 'Enabling…' : 'Enable' }}
      </button>
      <button @click="dismiss" class="icon-btn" title="Dismiss">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { usePushStore } from '../stores/push'

const push = usePushStore()
const dismissed = ref(localStorage.getItem('push_banner_dismissed') === '1')

const show = computed(() => {
  if (!push.supported) return false
  if (push.subscribed) return false
  if (dismissed.value) return false
  return true
})

function dismiss() {
  dismissed.value = true
  localStorage.setItem('push_banner_dismissed', '1')
}

async function onEnable() {
  const ok = await push.enable()
  if (ok) {
    localStorage.removeItem('push_banner_dismissed')
  }
}

onMounted(() => {
  push.refresh()
})
</script>

<style scoped>
.push-banner {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 16px;
  margin: 0 0 1.25rem 0;
  background: color-mix(in oklab, var(--signal) 6%, var(--bg));
  border: 1px solid color-mix(in oklab, var(--signal) 28%, transparent);
  border-left: 4px solid var(--signal);
  border-radius: var(--radius);
}

.push-icon {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--signal);
  color: var(--signal-ink);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}

.push-copy { flex: 1 1 auto; min-width: 0; }
.push-title { font-weight: 700; font-size: 0.9375rem; color: var(--ink); line-height: 1.3; }
.push-sub { font-size: 0.8125rem; color: var(--ink-3); line-height: 1.4; margin-top: 3px; }
.push-sub strong { color: var(--ink); font-weight: 600; }
.push-error {
  font-size: 0.75rem;
  color: var(--bad);
  margin-top: 6px;
  letter-spacing: 0.02em;
}

.push-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}
.push-cta { height: 36px; padding: 0 14px; font-size: 0.8125rem; }

@media (max-width: 640px) {
  .push-banner { flex-wrap: wrap; }
  .push-actions { width: 100%; justify-content: flex-end; margin-top: 4px; }
}
</style>
