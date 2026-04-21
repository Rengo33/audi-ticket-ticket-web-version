<template>
  <div>
    <div class="view-head">
      <div>
        <div class="eyebrow">FC BAYERN FIXTURES</div>
        <h1 class="view-title">Games</h1>
      </div>
      <button @click="fetchGames" :disabled="loading" class="btn btn-ghost">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
        <span>{{ loading ? 'Loading…' : 'Refresh' }}</span>
      </button>
    </div>

    <div v-if="loading && games.length === 0" class="empty">
      <div class="empty-mark is-loading"><div class="spinner"></div></div>
      <h3>Loading fixtures</h3>
    </div>

    <div v-else-if="error" class="empty">
      <div class="empty-mark">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      </div>
      <h3>Failed to load games</h3>
      <p>{{ error }}</p>
      <button @click="fetchGames" class="btn btn-primary" style="margin-top: 1rem;">Retry</button>
    </div>

    <div v-else-if="games.length === 0" class="empty">
      <div class="empty-mark">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="9"/></svg>
      </div>
      <h3>No games found</h3>
      <p>Check back later for upcoming FC Bayern matches.</p>
    </div>

    <div v-else class="games-grid">
      <article
        v-for="game in games" :key="game.id"
        class="game-card" :class="['status-' + game.status, { 'has-scheduled': game.scheduled_count > 0 }]"
      >
        <div class="game-media">
          <img v-if="game.image_url" :src="game.image_url" :alt="game.title" loading="lazy" />
          <div v-else class="game-media-fallback">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18"/></svg>
          </div>
          <span class="game-status mono">{{ formatStatus(game.status) }}</span>
        </div>

        <div class="game-body">
          <h3 class="game-title">{{ game.opponent }}</h3>
          <p class="game-loc mono">{{ game.location }}</p>

          <dl class="game-meta">
            <div>
              <dt>Match</dt>
              <dd class="mono">{{ formatDate(game.match_date) }} · {{ game.match_time || '—' }}</dd>
            </div>
            <div v-if="game.sale_date">
              <dt>Sale</dt>
              <dd class="mono is-sale">{{ formatDate(game.sale_date) }} · {{ game.sale_time || '—' }}</dd>
            </div>
          </dl>
        </div>

        <div class="game-foot">
          <span v-if="game.scheduled_count > 0" class="scheduled-chip mono">
            <span class="live-dot"></span>
            {{ game.scheduled_count }} scheduled
          </span>
          <a v-if="game.is_available" :href="game.url" target="_blank" rel="noopener" class="btn btn-primary game-cta">
            Buy now
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
          </a>
          <button v-else @click="scheduleGame(game)" class="btn btn-primary game-cta" :disabled="scheduling === game.id">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            <span>{{ scheduling === game.id ? 'Scheduling…' : 'Schedule' }}</span>
          </button>
        </div>
      </article>
    </div>

    <!-- Schedule Modal -->
    <transition name="fade">
    <div v-if="showScheduleModal" class="modal-overlay" @click.self="showScheduleModal = false">
      <div class="modal">
        <header class="modal-header">
          <div>
            <div class="modal-title">Schedule task</div>
            <div class="modal-sub">{{ selectedGame?.opponent }} · {{ selectedGame?.location }}</div>
          </div>
          <button @click="showScheduleModal = false" class="icon-btn" aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </header>

        <div class="modal-body">
          <div class="sale-banner">
            <div>
              <div class="eyebrow">Sale starts</div>
              <div class="sale-banner-value mono">{{ formatDate(selectedGame?.sale_date) }} · {{ selectedGame?.sale_time }}</div>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Task</div>
            <div class="field-row">
              <div class="field">
                <label class="field-label">Quantity</label>
                <input v-model="scheduleQuantity" type="number" min="1" max="10">
              </div>
              <div class="field">
                <label class="field-label">Threads</label>
                <input v-model="scheduleThreads" type="number" min="1" max="20">
              </div>
            </div>
            <div class="field">
              <label class="field-label">Price category</label>
              <select v-model="schedulePriceCategory">
                <option v-for="(cat, i) in gamePriceOptions" :key="i" :value="i">{{ cat }}</option>
              </select>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Auto-checkout</div>
            <label class="check-row">
              <input type="checkbox" v-model="scheduleAutoCheckout">
              <span>Run ACO when tickets are carted</span>
            </label>
            <div v-if="scheduleAutoCheckout" class="profiles-list">
              <div class="field-label" style="margin-top: 10px;">Billing profiles <span class="field-hint">(round-robin)</span></div>
              <label v-for="p in billingProfiles" :key="p.id" class="check-row">
                <input type="checkbox" :value="p.id" v-model="scheduleBillingProfileIds">
                <span class="profile-name">{{ p.name }}</span>
                <span v-if="p.card_last4" class="mono profile-card">•••• {{ p.card_last4 }}</span>
              </label>
              <div v-if="billingProfiles.length === 0" class="profiles-empty mono">No profiles — add one in Billing.</div>
            </div>
          </div>
        </div>

        <footer class="modal-footer">
          <button @click="showScheduleModal = false" class="btn btn-ghost">Cancel</button>
          <button @click="confirmSchedule" class="btn btn-primary" :disabled="scheduling">
            {{ scheduling ? 'Scheduling…' : 'Confirm' }}
          </button>
        </footer>
      </div>
    </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { api } from '../stores/api';
import { PRICE_CATEGORIES } from '../constants';

const games = ref([]);
const loading = ref(false);
const error = ref(null);
const scheduling = ref(null);
const showScheduleModal = ref(false);
const selectedGame = ref(null);
const scheduleQuantity = ref(4);
const scheduleThreads = ref(2);
const schedulePriceCategory = ref(0);
const scheduleAutoCheckout = ref(false);
const scheduleBillingProfileIds = ref([]);
const billingProfiles = ref([]);

const gamePriceOptions = computed(() => {
  const scraped = selectedGame.value?.price_categories || [];
  const priceMap = {};
  for (const cat of scraped) {
    if (cat.name.includes('Block 237')) priceMap[0] = cat.price;
    else if (cat.name.includes('Block 136')) priceMap[1] = cat.price;
    else if (cat.name.includes('Block 328')) priceMap[2] = cat.price;
  }
  return PRICE_CATEGORIES.map((c, i) => {
    const price = priceMap[i];
    return price !== undefined ? `${c.label.split('(')[0].trim()} (${price.toFixed(2)}€)` : c.label;
  });
});

const fetchGames = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await api.get('/api/games');
    games.value = response.games || response || [];
  } catch (e) {
    error.value = e.message || 'Failed to fetch games';
  } finally {
    loading.value = false;
  }
};
const formatDate = (dateStr) => {
  if (!dateStr) return 'TBD';
  try {
    const s = typeof dateStr === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(dateStr) && !dateStr.endsWith('Z')
      ? dateStr + 'Z' : dateStr;
    return new Date(s).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' });
  } catch { return dateStr; }
};

const formatStatus = (status) => ({
  'available':     'ON SALE',
  'upcoming':      'COMING SOON',
  'sold_out':      'SOLD OUT',
  'not_available': 'N/A'
}[status] || status);

const scheduleGame = (game) => {
  selectedGame.value = game;
  scheduleQuantity.value = 4;
  scheduleThreads.value = 2;
  schedulePriceCategory.value = 0;
  scheduleAutoCheckout.value = false;
  scheduleBillingProfileIds.value = [];
  showScheduleModal.value = true;
};

const confirmSchedule = async () => {
  if (!selectedGame.value) return;
  scheduling.value = selectedGame.value.id;
  try {
    await api.post('/api/games/schedule', {
      game_id: selectedGame.value.id,
      quantity: parseInt(scheduleQuantity.value),
      num_threads: parseInt(scheduleThreads.value),
      price_category: parseInt(schedulePriceCategory.value),
      auto_checkout: scheduleAutoCheckout.value,
      billing_profile_id: scheduleAutoCheckout.value ? scheduleBillingProfileIds.value.join(',') : null
    });
    await fetchGames();
    showScheduleModal.value = false;
  } catch (e) {
    alert('Failed to schedule: ' + (e.message || 'Unknown error'));
  } finally {
    scheduling.value = null;
  }
};

const fetchBillingProfiles = async () => {
  try { billingProfiles.value = await api.get('/api/billing/profiles'); } catch { /* ignore */ }
};

onMounted(() => { fetchGames(); fetchBillingProfiles(); });
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

.games-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
@media (min-width: 600px) { .games-grid { grid-template-columns: repeat(2, 1fr); gap: 16px; } }
@media (min-width: 1100px) { .games-grid { grid-template-columns: repeat(3, 1fr); } }

.game-card {
  display: flex; flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: border-color 0.15s, transform 0.15s;
}
.game-card:hover { border-color: color-mix(in oklab, var(--ink) 30%, var(--line)); }
.game-card.has-scheduled {
  box-shadow: inset 3px 0 0 var(--ok);
}

.game-media {
  position: relative;
  aspect-ratio: 16 / 9;
  background: var(--bg-subtle);
  overflow: hidden;
}
.game-media img {
  width: 100%; height: 100%; object-fit: cover;
  filter: saturate(1.05) contrast(1.02);
}
.game-media-fallback {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  color: var(--ink-4);
  opacity: 0.5;
}

.game-status {
  position: absolute;
  top: 10px; left: 10px;
  padding: 4px 8px;
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: 4px;
}
.status-available .game-status { background: var(--ok); color: white; border-color: transparent; }
.status-sold_out .game-status { background: var(--bad); color: white; border-color: transparent; }
.status-upcoming .game-status { background: var(--warn); color: white; border-color: transparent; }

.game-body { padding: 14px 14px 10px; flex: 1; display: flex; flex-direction: column; gap: 10px; }
.game-title {
  font-size: 1rem; font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.3;
  color: var(--ink);
}
.game-loc {
  font-size: 0.75rem;
  color: var(--ink-4);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.game-meta { display: flex; flex-direction: column; gap: 0; margin-top: auto; }
.game-meta > div {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 0;
  border-top: 1px solid var(--line-soft);
}
.game-meta dt {
  font-family: var(--font-mono);
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-4);
}
.game-meta dd {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--ink);
}
.game-meta dd.is-sale { color: var(--signal); }
[data-theme="dark"] .game-meta dd.is-sale { color: var(--signal); }

.game-foot {
  padding: 10px 14px 14px;
  display: flex; gap: 8px; align-items: center;
  border-top: 1px solid var(--line-soft);
}
.game-cta { flex: 1; height: 42px; }
.scheduled-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 10px;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--ok);
  background: var(--ok-soft);
  border-radius: 999px;
}

/* Sale banner in modal */
.sale-banner {
  padding: 12px 14px;
  background: var(--signal-soft);
  border: 1px solid color-mix(in oklab, var(--signal) 40%, transparent);
  border-radius: var(--radius);
  margin-bottom: 14px;
}
.sale-banner-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--ink);
  margin-top: 2px;
}

.field-hint { color: var(--ink-4); font-weight: 400; margin-left: 4px; text-transform: none; letter-spacing: 0; }
.profiles-list { display: flex; flex-direction: column; gap: 6px; }
.profile-name { flex: 1; }
.profile-card { color: var(--ink-3); font-size: 0.75rem; }
.profiles-empty {
  padding: 12px;
  color: var(--ink-4);
  font-size: 0.75rem;
  text-align: center;
  background: var(--surface-2);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

.spinner {
  width: 18px; height: 18px;
  border: 2px solid var(--line);
  border-top-color: var(--ink);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
