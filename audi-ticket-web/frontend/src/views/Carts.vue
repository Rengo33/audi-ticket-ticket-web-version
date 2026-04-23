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
      <article v-for="cart in cartStore.validCarts" :key="cart.token" class="cart-card" :class="{ 'is-critical': getRemaining(cart) < 180 && cart.checkout_status === 'pending' }">
        <div class="cart-top">
          <div class="cart-timer">
            <span class="cart-timer-label mono">Expires in</span>
            <span class="cart-timer-value mono tnum">{{ formatTime(cart.expires_at) }}</span>
          </div>
          <span class="badge" :class="statusBadgeClass(cart)">
            <span class="live-dot" v-if="isLiveStatus(cart)"></span>
            {{ statusLabel(cart) }}
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
          <div v-if="cart.billing_profile_name && cart.checkout_status === 'completed'" class="cart-profile mono">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            {{ cart.billing_profile_name }}
          </div>
          <div v-if="cart.checkout_error" class="cart-error mono">{{ cart.checkout_error }}</div>
        </div>

        <div class="cart-actions">
          <button @click="copyCookie(cart)" class="btn btn-ghost">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 10c-.5-3-2.7-5.3-5.5-6A9 9 0 1 0 21 14c0-.5 0-1 0-1.5-.5.5-1.5 1-2.5 1s-2-1-2-2c0-.8-.5-1.5-1.5-1.5S12 9.5 12 10.5c0 .8-.5 1.5-1.5 1.5S9 11.3 9 10.5"/></svg>
            <span>Cookie</span>
          </button>
          <template v-if="cart.checkout_status === 'pending' || cart.checkout_status === 'failed'">
            <button @click="openCheckoutModal(cart)" class="btn btn-primary cart-cta">
              {{ cart.checkout_status === 'failed' ? 'Retry' : 'Checkout' }}
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
            </button>
            <a :href="getCheckoutUrl(cart)" target="_blank" rel="noopener" class="btn btn-ghost cart-cta">
              Manual
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 17L17 7M7 7h10v10"/></svg>
            </a>
          </template>
          <a v-else-if="cart.invoice_url" :href="cart.invoice_url" target="_blank" rel="noopener" class="btn btn-primary cart-cta">
            Invoice
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 17L17 7M7 7h10v10"/></svg>
          </a>
          <a v-else :href="getCheckoutUrl(cart)" target="_blank" rel="noopener" class="btn btn-ghost cart-cta">
            Open checkout
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 17L17 7M7 7h10v10"/></svg>
          </a>
        </div>
      </article>
    </div>

    <transition name="fade">
      <div v-if="checkoutCart" class="modal-overlay" @click.self="closeCheckoutModal">
        <div class="modal checkout-modal">
          <header class="modal-header">
            <div>
              <div class="modal-title">Pick a profile</div>
              <div class="modal-sub mono">Cart #{{ checkoutCart.id }} · {{ getDisplayName(checkoutCart.product_url) }}</div>
            </div>
            <button @click="closeCheckoutModal" class="icon-btn" aria-label="Close">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </header>
          <div class="modal-body profile-picker">
            <div v-if="profilesLoading" class="empty"><div class="empty-mark is-loading"><div class="spinner"></div></div><h3>Loading profiles…</h3></div>
            <div v-else-if="profiles.length === 0" class="empty"><h3>No profiles yet</h3><p>Create a billing profile first.</p></div>
            <button
              v-else
              v-for="p in profiles"
              :key="p.id"
              @click="selectProfile(p)"
              class="profile-pick-row"
              :class="{ 'is-used': usedProfileIds.has(p.id) }"
              :disabled="submittingProfileId !== null"
            >
              <div class="profile-avatar mono">{{ initials(p.firstname, p.lastname) }}</div>
              <div class="profile-pick-body">
                <div class="profile-pick-top">
                  <span class="profile-pick-name">{{ p.name }}</span>
                  <span v-if="usedProfileIds.has(p.id)" class="used-tag mono">USED</span>
                </div>
                <div class="profile-pick-sub mono">{{ p.firstname }} {{ p.lastname }} · {{ p.email }}</div>
              </div>
              <div class="profile-pick-chevron" v-if="submittingProfileId !== p.id">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 6l6 6-6 6"/></svg>
              </div>
              <div v-else class="spinner"></div>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <transition name="toast">
      <div v-if="toastMessage" class="toast mono">{{ toastMessage }}</div>
    </transition>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import { useCartStore } from '../stores/cart';
import { api } from '../stores/api';
import { priceCategoryLabel } from '../constants';

const cartStore = useCartStore();
const toastMessage = ref('');

// Checkout modal state
const checkoutCart = ref(null);
const profiles = ref([]);
const usedProfileIds = ref(new Set());
const profilesLoading = ref(false);
const submittingProfileId = ref(null);

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
  setTimeout(() => { toastMessage.value = ''; }, 2400);
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

// Status chip helpers — one source of truth for label + color.
const STATUS_MAP = {
  pending: { label: 'HELD', cls: 'badge-running', live: true },
  running: { label: 'RUNNING', cls: 'badge-running', live: true },
  billing_done: { label: 'BILLING ✓', cls: 'badge-running', live: true },
  payment_confirmed: { label: 'PAYMENT ✓', cls: 'badge-running', live: true },
  completed: { label: 'COMPLETED', cls: 'badge-success', live: false },
  failed: { label: 'FAILED', cls: 'badge-failed', live: false },
};
const statusLabel = (cart) => {
  if (cart.checkout_status === 'pending' && getRemaining(cart) < 180) return 'CRITICAL';
  return (STATUS_MAP[cart.checkout_status] || STATUS_MAP.pending).label;
};
const statusBadgeClass = (cart) => {
  if (cart.checkout_status === 'pending' && getRemaining(cart) < 180) return 'badge-failed';
  return (STATUS_MAP[cart.checkout_status] || STATUS_MAP.pending).cls;
};
const isLiveStatus = (cart) => (STATUS_MAP[cart.checkout_status] || STATUS_MAP.pending).live;

const initials = (first = '', last = '') => ((first[0] || '') + (last[0] || '')).toUpperCase() || '—';

const openCheckoutModal = async (cart) => {
  checkoutCart.value = cart;
  profilesLoading.value = true;
  profiles.value = [];
  usedProfileIds.value = new Set();
  try {
    const [profs, usage] = await Promise.all([
      api.get('/api/billing/profiles'),
      api.get(`/api/billing/profiles/usage?event_id=${encodeURIComponent(cart.event_id || '')}`),
    ]);
    profiles.value = profs;
    usedProfileIds.value = new Set(usage.filter(u => u.used).map(u => u.profile_id));
  } catch (e) {
    flash('Failed to load profiles');
    checkoutCart.value = null;
  } finally {
    profilesLoading.value = false;
  }
};

const closeCheckoutModal = () => {
  if (submittingProfileId.value !== null) return;
  checkoutCart.value = null;
  profiles.value = [];
  usedProfileIds.value = new Set();
};

const selectProfile = async (profile) => {
  if (!checkoutCart.value) return;
  if (usedProfileIds.value.has(profile.id)) {
    if (!confirm(`${profile.name} already checked out for this event. Run again anyway?`)) return;
  }
  submittingProfileId.value = profile.id;
  try {
    const res = await cartStore.triggerCheckout(checkoutCart.value.id, profile.id);
    if (res && res.success) {
      flash(`Checkout started with ${profile.name}`);
    } else {
      flash(`Checkout failed: ${res?.message || 'unknown'}`);
    }
    checkoutCart.value = null;
  } catch (e) {
    flash(`Error: ${e.message || 'request failed'}`);
  } finally {
    submittingProfileId.value = null;
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

.cart-profile {
  margin-top: 8px;
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 8px;
  border-radius: 999px;
  background: color-mix(in oklab, var(--ok) 14%, transparent);
  color: var(--ok);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.cart-error {
  margin-top: 8px;
  font-size: 0.6875rem;
  color: var(--bad);
  word-break: break-word;
}

/* Profile picker modal */
.checkout-modal { max-width: 460px; }
.profile-picker { padding: 8px; display: flex; flex-direction: column; gap: 6px; }
.profile-pick-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
  font-family: inherit;
}
.profile-pick-row:hover:not(:disabled) {
  border-color: color-mix(in oklab, var(--ink) 30%, var(--line));
  background: var(--surface-2, var(--surface));
}
.profile-pick-row:disabled { opacity: 0.6; cursor: not-allowed; }
.profile-pick-row.is-used { background: color-mix(in oklab, var(--warn) 6%, transparent); }
.profile-avatar {
  width: 36px; height: 36px; flex-shrink: 0;
  border-radius: 50%;
  background: var(--line-soft);
  color: var(--ink-2);
  display: flex; align-items: center; justify-content: center;
  font-size: 0.75rem; font-weight: 700;
  letter-spacing: 0.04em;
}
.profile-pick-body { flex: 1; min-width: 0; }
.profile-pick-top { display: flex; align-items: center; gap: 8px; }
.profile-pick-name { font-size: 0.9375rem; font-weight: 700; color: var(--ink); }
.used-tag {
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--warn);
  color: white;
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.06em;
}
.profile-pick-sub {
  font-size: 0.75rem;
  color: var(--ink-3);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  margin-top: 2px;
}
.profile-pick-chevron { color: var(--ink-4); flex-shrink: 0; }

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
