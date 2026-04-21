<template>
  <div>
    <div class="view-head">
      <div>
        <div class="eyebrow">ACTIVE RESERVATIONS</div>
        <h1 class="view-title">Carts</h1>
      </div>
      <div class="ws-chip mono">
        <span class="live-dot"></span>
        {{ cartStore.validCarts.length }} live
      </div>
    </div>

    <div v-if="cartStore.loading && cartStore.carts.length === 0" class="empty">
      <div class="empty-mark is-loading"><div class="spinner"></div></div>
      <h3>Loading carts…</h3>
    </div>

    <div v-else-if="cartStore.validCarts.length === 0" class="empty">
      <div class="empty-mark">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M2 4h3l2.5 12h12"/><path d="M7.5 16h12L22 7H6"/><circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/></svg>
      </div>
      <h3>No active carts</h3>
      <p>Carts expire after 17 minutes. Start a task to grab tickets.</p>
    </div>

    <div v-else class="carts-grid">
      <article v-for="cart in cartStore.validCarts" :key="cart.token" class="cart-card" :class="{ 'is-critical': getRemaining(cart) < 180 }">
        <div class="cart-top">
          <div class="cart-timer">
            <span class="cart-timer-label mono">Expires in</span>
            <span class="cart-timer-value mono tnum">{{ formatTime(cart.expires_at) }}</span>
          </div>
          <span class="badge" :class="getRemaining(cart) < 180 ? 'badge-failed' : 'badge-running'">
            <span class="live-dot"></span>
            {{ getRemaining(cart) < 180 ? 'CRITICAL' : 'HELD' }}
          </span>
        </div>

        <div class="progress-track">
          <div class="progress-fill" :style="{ width: getProgress(cart.expires_at) + '%' }"></div>
        </div>

        <div class="cart-body">
          <h3 class="cart-title">
            <span v-if="cart.auto_checkout" class="aco-tag mono">[ACO]</span>
            {{ getDisplayName(cart.product_url || cart.checkout_url) }}
          </h3>
          <div class="cart-meta mono">
            <span>{{ cart.quantity }}× tix</span>
            <span class="dot-sep">·</span>
            <span>{{ priceCategoryLabel(cart.price_category) }}</span>
            <span v-if="cart.total_time" class="dot-sep">·</span>
            <span v-if="cart.total_time">{{ cart.total_time.toFixed(2) }}s</span>
          </div>
        </div>

        <div class="cart-actions">
          <button @click="copyCookie(cart)" class="btn btn-ghost">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 10c-.5-3-2.7-5.3-5.5-6A9 9 0 1 0 21 14c0-.5 0-1 0-1.5-.5.5-1.5 1-2.5 1s-2-1-2-2c0-.8-.5-1.5-1.5-1.5S12 9.5 12 10.5c0 .8-.5 1.5-1.5 1.5S9 11.3 9 10.5"/></svg>
            <span>Copy cookie</span>
          </button>
          <a :href="getCheckoutUrl(cart)" target="_blank" rel="noopener" class="btn btn-primary cart-cta">
            Open checkout
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 17L17 7M7 7h10v10"/></svg>
          </a>
        </div>
      </article>
    </div>

    <transition name="toast">
      <div v-if="toastMessage" class="toast mono">{{ toastMessage }}</div>
    </transition>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import { useCartStore } from '../stores/cart';
import { priceCategoryLabel } from '../constants';

const cartStore = useCartStore();
const toastMessage = ref('');

const getDisplayName = (url) => {
  try {
    if (!url) return 'Ticket';
    const parts = url.split('/');
    const last = parts.filter(Boolean).pop() || '';
    if (last) return last.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    return 'Ticket';
  } catch { return 'Ticket'; }
};

const getCheckoutUrl = (cart) => cart.token ? `/checkout/${cart.token}/cart` : '#';

const flash = (msg) => {
  toastMessage.value = msg;
  setTimeout(() => { toastMessage.value = ''; }, 1800);
};

const copyToClipboard = (text) => {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text);
    return;
  }
  window.prompt('Cmd+C / Ctrl+C to copy:', text);
};

const copyCookie = async (cart) => {
  try {
    const resp = await fetch(`/api/checkout/${cart.token}/cookie`);
    if (!resp.ok) { flash('Could not fetch cookie'); return; }
    const data = await resp.json();
    copyToClipboard(data.value);
    flash('Cookie copied');
  } catch {
    flash('Error copying cookie');
  }
};

// These helpers all touch cartStore.tick so the template re-evaluates each
// second while cart identity stays stable (avoiding full card re-renders).
const formatTime = (expiryDate) => {
  cartStore.tick;
  const diff = Math.max(0, expiryDate.getTime() - Date.now());
  const m = Math.floor(diff / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const getRemaining = (cart) => {
  cartStore.tick;
  return Math.floor(Math.max(0, cart.expires_at.getTime() - Date.now()) / 1000);
};

const getProgress = (expiryDate) => {
  cartStore.tick;
  const remaining = Math.max(0, expiryDate.getTime() - Date.now());
  return Math.min(100, (remaining / (17 * 60 * 1000)) * 100);
};

let timer;
onMounted(async () => {
  await cartStore.fetchCarts();
  timer = setInterval(() => { cartStore.triggerUpdate(); }, 1000);
});
onUnmounted(() => { if (timer) clearInterval(timer); });
</script>

<style scoped>
.view-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.view-title {
  font-size: clamp(1.5rem, 4vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin-top: 4px;
}
.ws-chip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--ink-2);
  background: var(--surface);
}

.carts-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
@media (min-width: 640px) { .carts-grid { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1100px) { .carts-grid { grid-template-columns: repeat(3, 1fr); } }

.cart-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex; flex-direction: column;
  transition: border-color 0.15s;
}
.cart-card.is-critical { border-color: color-mix(in oklab, var(--bad) 40%, var(--line)); }

.cart-top {
  padding: 14px 16px 10px;
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px;
}

.cart-timer { display: flex; flex-direction: column; }
.cart-timer-label {
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-4);
}
.cart-timer-value {
  font-size: 1.875rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--ink);
  margin-top: -2px;
  line-height: 1;
}
.is-critical .cart-timer-value { color: var(--bad); }

.progress-track {
  height: 3px;
  background: var(--line-soft);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--signal);
  transition: width 1s linear;
}
.is-critical .progress-fill { background: var(--bad); }

.cart-body { padding: 12px 16px; flex: 1; }
.cart-title {
  font-size: 0.9375rem; font-weight: 700;
  letter-spacing: -0.005em;
  color: var(--ink);
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.aco-tag {
  display: inline-block;
  margin-right: 6px;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--signal-soft);
  color: var(--signal);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  vertical-align: 2px;
}
.cart-meta {
  font-size: 0.75rem;
  color: var(--ink-3);
  display: flex; gap: 6px; flex-wrap: wrap;
}
.dot-sep { color: var(--ink-4); }

.cart-actions {
  padding: 10px 12px 12px;
  display: flex;
  gap: 6px;
  border-top: 1px solid var(--line-soft);
}
.cart-actions .btn { height: 40px; font-size: 0.8125rem; flex: 1; }
.cart-cta { flex: 2; }

.spinner {
  width: 18px; height: 18px;
  border: 2px solid var(--line);
  border-top-color: var(--ink);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.toast {
  position: fixed;
  bottom: calc(80px + var(--safe-b));
  left: 50%; transform: translateX(-50%);
  padding: 10px 18px;
  border-radius: 999px;
  background: var(--ink);
  color: var(--bg);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  box-shadow: var(--shadow-modal);
  z-index: 100;
}
@media (min-width: 900px) { .toast { bottom: 24px; } }
.toast-enter-active, .toast-leave-active { transition: opacity 0.2s, transform 0.2s; }
.toast-enter-from { opacity: 0; transform: translateX(-50%) translateY(8px); }
.toast-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }
</style>
