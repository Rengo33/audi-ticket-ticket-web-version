<template>
  <div class="carts-view">
    <!-- Header/Title handled by parent or just internal title -->

    <div v-if="cartStore.loading && cartStore.carts.length === 0" class="loading-state">
        Loading carts...
    </div>

    <div v-else-if="cartStore.validCarts.length === 0" class="empty-state">
      <div class="empty-icon">🛒</div>
      <h3>No Active Carts</h3>
      <p>Carts expire after 17 minutes. Start a task to grab tickets.</p>
    </div>

    <div v-else class="carts-grid">
      <div v-for="cart in cartStore.validCarts" :key="cart.token" class="cart-card">
        <div class="card-header-blue">
            <div class="timer-badge">
              <span class="icon">⏰</span>
              <span class="time">{{ formatTime(new Date(cart.expires_at)) }}</span>
            </div>
        </div>

        <div class="card-content">
            <div class="blue-icon-circle">🛒</div>
            <div class="details">
                <!-- Fallback if product_url is missing, use checkout_url or generic -->
                <h3>{{ getDisplayName(cart.product_url || cart.checkout_url) }}</h3>
                <p class="meta">Qty: {{ cart.quantity }} • {{ priceCategoryLabel(cart.price_category) }} • {{ cart.total_time ? cart.total_time.toFixed(2) + 's' : '' }}</p>
            </div>
        </div>

        <div class="progress-bar-bg">
            <div class="progress-bar-fill" :style="{ width: getProgress(new Date(cart.expires_at)) + '%' }"></div>
        </div>

        <div class="card-actions">
            <button @click="copyScript(cart)" class="action-btn copy-btn">Script kopieren</button>
            <button @click="copyCookie(cart)" class="action-btn cookie-btn">Cookie kopieren</button>
            <a :href="getCheckoutUrl(cart)" target="_blank" class="action-btn proxy-btn">
                Proxy Checkout
            </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue';
import { useCartStore } from '../stores/cart';
import { priceCategoryLabel } from '../constants';

const cartStore = useCartStore();
const cookieCache = {};

const prefetchCookies = async () => {
    for (const cart of cartStore.validCarts) {
        if (cookieCache[cart.token]) continue;
        try {
            const resp = await fetch(`/api/checkout/${cart.token}/cookie`);
            if (resp.ok) cookieCache[cart.token] = await resp.json();
        } catch { /* ignore */ }
    }
};

const getDisplayName = (url) => {
    try {
        if (!url) return "Ticket Item";
        if (url.includes('audi-interaction.com')) {
           // Attempt to parse meaningful name from URL if possible
           // e.g. /event/foo-bar
           const parts = url.split('/');
           const last = parts[parts.length - 1] || parts[parts.length - 2];
           if (last) return last.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }
        return "Ticket Item";
    } catch { return "Ticket Item"; }
};

const getCheckoutUrl = (cart) => {
    if (cart.token) return `/checkout/${cart.token}/cart`;
    return '#';
};

const copyToClipboard = (text) => {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text);
        return;
    }
    // HTTP fallback: prompt with pre-selected text
    window.prompt('Cmd+C / Strg+C zum Kopieren:', text);
};

const copyScript = (cart) => {
    const data = cookieCache[cart.token];
    if (!data) { flash('Laden... nochmal versuchen'); prefetchCookies(); return; }
    const script = `document.cookie='${data.name}=${data.value};path=/;domain=.audidefuehrungen2.regiondo.de';location.href='${data.checkout_url}'`;
    copyToClipboard(script);
    flash('Script kopiert!');
};

const copyCookie = (cart) => {
    const data = cookieCache[cart.token];
    if (!data) { flash('Laden... nochmal versuchen'); prefetchCookies(); return; }
    copyToClipboard(data.value);
    flash('Cookie kopiert!');
};

const flash = (msg) => {
    const el = document.createElement('div');
    el.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#34c759;color:white;padding:10px 24px;border-radius:10px;font-weight:600;z-index:999;';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2000);
};

const formatTime = (expiryDate) => {
    const now = new Date();
    const diff = Math.max(0, expiryDate - now);
    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

const getProgress = (expiryDate) => {
    const now = new Date();
    const totalDuration = 17 * 60 * 1000; // 17 minutes
    const remaining = Math.max(0, expiryDate - now);
    return Math.min(100, (remaining / totalDuration) * 100);
};

let timer;
onMounted(async () => {
    await cartStore.fetchCarts();
    prefetchCookies();
    timer = setInterval(() => {
        cartStore.triggerUpdate();
    }, 1000);
});

onUnmounted(() => {
    if (timer) clearInterval(timer);
});
</script>

<style scoped>
.carts-view {
    padding: 1rem;
}

.carts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1.5rem;
}

.cart-card {
    background: var(--card-bg);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 20px var(--card-shadow);
    border: 1px solid var(--border-light);
    display: flex;
    flex-direction: column;
}

.card-header-blue {
    padding: 1rem;
    display: flex;
    justify-content: flex-end;
}

.timer-badge {
    background: rgba(0, 122, 255, 0.1);
    color: var(--accent-blue);
    padding: 6px 12px;
    border-radius: 8px;
    font-weight: 700;
    font-family: monospace;
    display: flex;
    gap: 6px;
    align-items: center;
}

.card-content {
    padding: 0 1.5rem 1.5rem;
    display: flex;
    gap: 1rem;
    align-items: center;
    flex-grow: 1;
}

.blue-icon-circle {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: rgba(0, 122, 255, 0.1);
    color: var(--accent-blue);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    flex-shrink: 0;
}

.details h3 {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0 0 4px 0;
    color: var(--text-primary);
}

.meta {
    color: var(--text-secondary);
    font-size: 0.9rem;
    margin: 0;
}

.progress-bar-bg {
    height: 4px;
    background: var(--border-light);
    width: 100%;
}

.progress-bar-fill {
    height: 100%;
    background: var(--accent-blue);
    transition: width 1s linear;
}

.card-actions {
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.action-btn {
    display: block;
    width: 100%;
    padding: 12px;
    text-align: center;
    text-decoration: none;
    font-weight: 600;
    font-size: 0.9rem;
    border-radius: 10px;
    border: none;
    cursor: pointer;
    transition: opacity 0.2s;
    color: white;
}

.action-btn:hover { opacity: 0.85; }

.copy-btn { background: var(--success); }
.cookie-btn { background: var(--accent-blue); }
.proxy-btn { background: var(--text-tertiary); font-size: 0.8rem; }

.empty-state {
    text-align: center;
    padding: 4rem 2rem;
    color: var(--text-secondary);
}

.empty-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
    opacity: 0.6;
}

.loading-state {
    text-align: center;
    padding: 2rem;
    color: var(--text-secondary);
}

@media (max-width: 768px) {
  .carts-grid { grid-template-columns: 1fr; }
}
</style>
