<template>
  <div class="games-view">
    <div class="toolbar">
      <button @click="refreshGames" :disabled="loading" class="refresh-btn">
        {{ loading ? 'Loading...' : '↻ Refresh' }}
      </button>
    </div>

    <div v-if="loading && games.length === 0" class="loading-state">
      <div class="spinner"></div>
      <p>Loading games...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <div class="error-icon">⚠️</div>
      <h3>Failed to load games</h3>
      <p>{{ error }}</p>
      <button @click="refreshGames" class="retry-btn">Try Again</button>
    </div>

    <div v-else-if="games.length === 0" class="empty-state">
      <div class="empty-icon">⚽</div>
      <h3>No Games Found</h3>
      <p>Check back later for upcoming FC Bayern matches.</p>
    </div>

    <div v-else class="games-grid">
      <div v-for="game in games" :key="game.id" class="game-card" :class="{ 'scheduled': game.is_scheduled }">
        <div class="card-image" v-if="game.image_url">
          <img :src="game.image_url" :alt="game.title" />
          <div class="status-overlay" :class="game.status">
            {{ formatStatus(game.status) }}
          </div>
        </div>
        <div class="card-image placeholder" v-else>
          <span>⚽</span>
          <div class="status-overlay" :class="game.status">
            {{ formatStatus(game.status) }}
          </div>
        </div>

        <div class="card-body">
          <h3>{{ game.opponent }}</h3>
          <p class="location">{{ game.location }}</p>

          <div class="match-info">
            <div class="info-item">
              <span class="label">Match</span>
              <span class="value">{{ formatDate(game.match_date) }} {{ game.match_time || '' }}</span>
            </div>
            <div class="info-item" v-if="game.sale_date">
              <span class="label">Sale</span>
              <span class="value sale-date">{{ formatDate(game.sale_date) }} {{ game.sale_time || '' }}</span>
            </div>
            <div class="info-item prices" v-if="game.price_categories && game.price_categories.length">
              <span class="label">Prices</span>
              <span class="value price-list">
                <span v-for="(cat, i) in game.price_categories" :key="i" class="price-tag">
                  {{ cat.name.replace('Kategorie ', 'Kat ') }}: {{ cat.price }}€
                </span>
              </span>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <div v-if="game.scheduled_count > 0" class="scheduled-badge">
            {{ game.scheduled_count }} task{{ game.scheduled_count > 1 ? 's' : '' }} scheduled
          </div>
          <button
            v-if="!game.is_available"
            @click="scheduleGame(game)"
            class="schedule-btn"
            :disabled="scheduling === game.id"
          >
            {{ scheduling === game.id ? 'Scheduling...' : '+ Schedule Task' }}
          </button>
          <a
            v-else
            :href="game.url"
            target="_blank"
            class="buy-btn"
          >
            Buy Now →
          </a>
        </div>
      </div>
    </div>

    <!-- Schedule Modal -->
    <div v-if="showScheduleModal" class="modal-overlay" @click.self="showScheduleModal = false">
      <div class="modal">
        <h3>Schedule Task</h3>
        <p class="modal-subtitle">for {{ selectedGame?.opponent }}</p>

        <div class="form-group">
          <label>Quantity</label>
          <input v-model="scheduleQuantity" type="number" min="1" max="10">
        </div>
        <div class="form-group">
          <label>Threads</label>
          <input v-model="scheduleThreads" type="number" min="1" max="20">
        </div>
        <div class="form-group">
          <label>Price Category</label>
          <select v-model="schedulePriceCategory">
            <option v-for="cat in PRICE_CATEGORIES" :key="cat.value" :value="cat.value">{{ cat.label }}</option>
          </select>
        </div>

        <div class="form-group">
          <label class="toggle-label">
            <input type="checkbox" v-model="scheduleAutoCheckout">
            Auto Checkout (ACO)
          </label>
        </div>
        <div class="form-group" v-if="scheduleAutoCheckout">
          <label>Billing Profiles (round-robin)</label>
          <div class="profile-checkboxes">
            <label v-for="p in billingProfiles" :key="p.id" class="profile-check">
              <input type="checkbox" :value="p.id" v-model="scheduleBillingProfileIds">
              {{ p.name }} <span class="card-hint">{{ p.card_last4 ? '••••' + p.card_last4 : '' }}</span>
            </label>
          </div>
        </div>

        <div class="sale-info">
          <span class="label">Sale starts:</span>
          <span class="value">{{ formatDate(selectedGame?.sale_date) }} {{ selectedGame?.sale_time }}</span>
        </div>

        <div class="modal-actions">
          <button @click="showScheduleModal = false" class="cancel-btn">Cancel</button>
          <button @click="confirmSchedule" class="confirm-btn" :disabled="scheduling">
            {{ scheduling ? 'Scheduling...' : 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
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

const fetchGames = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await api.get('/api/games');
    games.value = response.games || response || [];
  } catch (e) {
    error.value = e.message || 'Failed to fetch games';
    console.error('Failed to fetch games:', e);
  } finally {
    loading.value = false;
  }
};

const refreshGames = () => {
  fetchGames();
};

const formatDate = (dateStr) => {
  if (!dateStr) return 'TBD';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  } catch {
    return dateStr;
  }
};

const formatStatus = (status) => {
  const statusMap = {
    'available': 'On Sale',
    'upcoming': 'Coming Soon',
    'sold_out': 'Sold Out',
    'not_available': 'Not Available'
  };
  return statusMap[status] || status;
};

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
    const response = await api.post('/api/games/schedule', {
      game_id: selectedGame.value.id,
      quantity: parseInt(scheduleQuantity.value),
      num_threads: parseInt(scheduleThreads.value),
      price_category: parseInt(schedulePriceCategory.value),
      auto_checkout: scheduleAutoCheckout.value,
      billing_profile_id: scheduleAutoCheckout.value ? scheduleBillingProfileIds.value.join(',') : null
    });

    // Refresh games to update scheduled count
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

onMounted(() => {
  fetchGames();
  fetchBillingProfiles();
});
</script>

<style scoped>
.toolbar { margin-bottom: 2rem; display: flex; justify-content: flex-end; }
.refresh-btn { background: var(--hover-bg); color: var(--text-primary); padding: 12px 24px; border-radius: 12px; font-weight: 600; cursor: pointer; border: none; transition: 0.2s; }
.refresh-btn:hover { background: var(--border-light); }
.refresh-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.games-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem; }

.game-card { background: var(--card-bg); border-radius: 16px; overflow: hidden; transition: transform 0.2s, box-shadow 0.2s; border: 1px solid var(--border-light); }
.game-card:hover { transform: translateY(-2px); box-shadow: 0 10px 30px var(--card-shadow); }
.game-card.scheduled { border-color: var(--success); }

.card-image { position: relative; height: 160px; background: linear-gradient(135deg, var(--card-image-gradient-start), var(--card-image-gradient-end)); overflow: hidden; }
.card-image img { width: 100%; height: 100%; object-fit: cover; }
.card-image.placeholder { display: flex; align-items: center; justify-content: center; font-size: 3rem; opacity: 0.3; }

.status-overlay { position: absolute; top: 12px; right: 12px; padding: 6px 12px; border-radius: 8px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
.status-overlay.available { background: #34c759; color: white; }
.status-overlay.upcoming { background: #ff9500; color: white; }
.status-overlay.sold_out { background: #ff3b30; color: white; }
.status-overlay.not_available { background: #8e8e93; color: white; }

.card-body { padding: 1.25rem; }
.card-body h3 { font-size: 1.15rem; font-weight: 700; margin-bottom: 4px; color: var(--text-primary); }
.location { color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1rem; }

.match-info { background: var(--stat-bg); padding: 12px; border-radius: 10px; }
.info-item { display: flex; justify-content: space-between; align-items: center; }
.info-item + .info-item { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border-light); }
.info-item .label { font-size: 0.8rem; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.3px; }
.info-item .value { font-size: 0.9rem; font-weight: 600; color: var(--text-primary); }
.info-item .sale-date { color: var(--accent-blue); }
.info-item.prices { flex-direction: column; align-items: flex-start; gap: 4px; }
.price-list { display: flex; flex-wrap: wrap; gap: 4px; }
.price-tag { background: var(--hover-bg); padding: 2px 8px; border-radius: 6px; font-size: 0.8rem; white-space: nowrap; }

.card-footer { padding: 0 1.25rem 1.25rem; }

.schedule-btn { width: 100%; padding: 14px; background: var(--btn-primary-bg); color: var(--btn-primary-text); border: none; border-radius: 12px; font-weight: 600; cursor: pointer; transition: 0.2s; }
.schedule-btn:hover { background: var(--btn-primary-hover); }
.schedule-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.buy-btn { display: block; width: 100%; padding: 14px; background: var(--success); color: white; border: none; border-radius: 12px; font-weight: 600; text-align: center; text-decoration: none; transition: 0.2s; }
.buy-btn:hover { background: #2db84d; }

.scheduled-badge { text-align: center; padding: 14px; background: rgba(52, 199, 89, 0.1); color: var(--success); border-radius: 12px; font-weight: 600; }

/* Loading & Empty States */
.loading-state, .empty-state, .error-state { text-align: center; padding: 4rem 2rem; color: var(--text-tertiary); }
.empty-icon, .error-icon { font-size: 3rem; margin-bottom: 1rem; opacity: 0.5; }
.spinner { width: 40px; height: 40px; border: 3px solid var(--border-light); border-top-color: var(--text-primary); border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1rem; }
@keyframes spin { to { transform: rotate(360deg); } }

.retry-btn { margin-top: 1rem; padding: 10px 20px; background: var(--btn-primary-bg); color: var(--btn-primary-text); border: none; border-radius: 8px; cursor: pointer; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: var(--modal-overlay); display: flex; align-items: center; justify-content: center; backdrop-filter: blur(5px); z-index: 100; }
.modal { background: var(--card-bg); padding: 2rem; border-radius: 20px; width: 100%; max-width: 400px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); }
.modal h3 { font-size: 1.4rem; font-weight: 700; margin-bottom: 0.25rem; }
.modal-subtitle { color: var(--text-tertiary); margin-bottom: 1.5rem; }

.form-group { margin-bottom: 1.25rem; }
.form-group label { display: block; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.5rem; color: var(--text-primary); }
.form-group input, .form-group select { width: 100%; padding: 12px; border: 1px solid var(--border-light); border-radius: 10px; font-size: 1rem; background: var(--input-bg); color: var(--text-primary); }
.toggle-label { display: flex; align-items: center; gap: 8px; font-weight: 600; cursor: pointer; }
.toggle-label input[type="checkbox"] { width: auto; }
.profile-checkboxes { display: flex; flex-direction: column; gap: 6px; }
.profile-check { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: var(--stat-bg); border-radius: 8px; cursor: pointer; font-size: 0.95rem; }
.profile-check input[type="checkbox"] { width: auto; }
.card-hint { color: var(--text-tertiary); font-size: 0.8rem; }

.sale-info { background: var(--hover-bg); padding: 12px; border-radius: 10px; display: flex; justify-content: space-between; margin-bottom: 1.5rem; }
.sale-info .label { color: var(--text-tertiary); font-size: 0.85rem; }
.sale-info .value { font-weight: 600; color: var(--accent-blue); }

.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; }
.cancel-btn { background: var(--hover-bg); color: var(--text-primary); border: none; padding: 12px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; }
.confirm-btn { background: var(--btn-primary-bg); color: var(--btn-primary-text); border: none; padding: 12px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; }
.confirm-btn:disabled { opacity: 0.6; }

@media (max-width: 768px) {
  .games-grid { grid-template-columns: 1fr; }
  .card-image { height: 120px; }
  .modal { max-width: 95vw; padding: 1.5rem; }
}
</style>
