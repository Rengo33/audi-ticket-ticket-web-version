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
                <p class="meta">Qty: {{ cart.quantity }} • Thread #{{ cart.thread_id || '?' }}</p>
            </div>
        </div>

        <div class="progress-bar-bg">
            <div class="progress-bar-fill" :style="{ width: getProgress(new Date(cart.expires_at)) + '%' }"></div>
        </div>

        <div class="card-actions">
            <!-- Ensure checkout_url is formed correctly if just a token or full URL -->
            <a :href="getCheckoutUrl(cart)" target="_blank" class="checkout-btn">
                Proceed to Checkout
            </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue';
import { useCartStore } from '../stores/cart';

const cartStore = useCartStore();

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
    if (cart.checkout_url) return cart.checkout_url;
    // Fallback based on old code: window.location.origin + /checkout/ + token ? 
    // Or maybe the backend provides a direct link. The old code had <a :href="/checkout/${cart.token}">
    // But usually checkout is external? 
    // Old code: href="`/checkout/${cart.token}`"
    // So it's an internal route that redirects? Or a proxy?
    // If the checkout_url is fully qualified from backend, use it. 
    // If not, construct it. The backend model in schemas.py might clarify, but let's be safe.
    if (cart.token) return `/checkout/${cart.token}`;
    return '#';
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
onMounted(() => {
    cartStore.fetchCarts();
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
    background: white; 
    border-radius: 16px; 
    overflow: hidden; 
    box-shadow: 0 4px 20px rgba(0,0,0,0.05); 
    border: 1px solid #e5e5ea; 
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
    color: #007AFF; 
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
    color: #007AFF; 
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
    color: #1c1c1e;
}

.meta { 
    color: #6c6c70; 
    font-size: 0.9rem; 
    margin: 0;
}

.progress-bar-bg { 
    height: 4px; 
    background: #e5e5ea; 
    width: 100%; 
}

.progress-bar-fill { 
    height: 100%; 
    background: #007AFF; 
    transition: width 1s linear; 
}

.card-actions { 
    padding: 0; 
}

.checkout-btn { 
    display: block; 
    width: 100%; 
    padding: 16px; 
    background: #007AFF; 
    color: white; 
    text-align: center; 
    text-decoration: none; 
    font-weight: 600; 
    font-size: 1rem; 
    transition: background 0.2s; 
}

.checkout-btn:hover { 
    background: #0056b3; 
}

.empty-state { 
    text-align: center; 
    padding: 4rem 2rem; 
    color: #6c6c70; 
}

.empty-icon { 
    font-size: 3rem; 
    margin-bottom: 1rem; 
    opacity: 0.6; 
}

.loading-state {
    text-align: center;
    padding: 2rem;
    color: #6c6c70;
}
</style>
