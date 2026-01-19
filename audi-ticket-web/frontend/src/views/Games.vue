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
          </div>
        </div>

        <div class="card-footer">
          <template v-if="game.is_scheduled">
            <div class="scheduled-badge">✓ Scheduled</div>
            <button @click="cancelScheduled(game)" class="cancel-schedule-btn" :disabled="cancelling === game.scheduled_task_id">
              {{ cancelling === game.scheduled_task_id ? 'Cancelling...' : 'Cancel Scheduled Task' }}
            </button>
          </template>
          <button 
            v-else-if="!game.is_available" 
            @click="scheduleGame(game)"
            class="schedule-btn"
            :disabled="scheduling === game.id"
          >
            {{ scheduling === game.id ? 'Scheduling...' : 'Schedule Task' }}
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

const games = ref([]);
const loading = ref(false);
const error = ref(null);
const scheduling = ref(null);
const cancelling = ref(null);
import { useScheduledStore } from '../stores/scheduled';
const scheduledStore = useScheduledStore();
const cancelScheduled = async (game) => {
  if (!game.scheduled_task_id) return;
  cancelling.value = game.scheduled_task_id;
  try {
    await api.delete(`/api/games/scheduled/${game.scheduled_task_id}`);
    // Update local state
    const idx = games.value.findIndex(g => g.id === game.id);
    if (idx !== -1) {
      games.value[idx].is_scheduled = false;
      games.value[idx].scheduled_task_id = null;
    }
  } catch (e) {
    alert('Failed to cancel: ' + (e.message || 'Unknown error'));
  } finally {
    cancelling.value = null;
  }
};
const showScheduleModal = ref(false);
const selectedGame = ref(null);
const scheduleQuantity = ref(4);
const scheduleThreads = ref(2);

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
  showScheduleModal.value = true;
};

const confirmSchedule = async () => {
  if (!selectedGame.value) return;
  
  scheduling.value = selectedGame.value.id;
  try {
    await api.post('/api/games/schedule', {
      game_id: selectedGame.value.id,
      quantity: parseInt(scheduleQuantity.value),
      num_threads: parseInt(scheduleThreads.value)
    });
    
    // Mark as scheduled locally
    const idx = games.value.findIndex(g => g.id === selectedGame.value.id);
    if (idx !== -1) {
      games.value[idx].is_scheduled = true;
    }
    
    showScheduleModal.value = false;
  } catch (e) {
    alert('Failed to schedule: ' + (e.message || 'Unknown error'));
  } finally {
    scheduling.value = null;
  }
};

onMounted(() => {
  fetchGames();
});
</script>

<style scoped>
.toolbar { margin-bottom: 2rem; display: flex; justify-content: flex-end; }
.refresh-btn { background: #f2f2f7; color: #1c1c1e; padding: 12px 24px; border-radius: 12px; font-weight: 600; cursor: pointer; border: none; transition: 0.2s; }
.refresh-btn:hover { background: #e5e5ea; }
.refresh-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.games-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem; }

.game-card { background: white; border-radius: 16px; overflow: hidden; transition: transform 0.2s, box-shadow 0.2s; border: 1px solid #e5e5ea; }
.game-card:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
.game-card.scheduled { border-color: #34c759; }

.card-image { position: relative; height: 160px; background: linear-gradient(135deg, #1c1c1e, #3a3a3c); overflow: hidden; }
.card-image img { width: 100%; height: 100%; object-fit: cover; }
.card-image.placeholder { display: flex; align-items: center; justify-content: center; font-size: 3rem; opacity: 0.3; }

.status-overlay { position: absolute; top: 12px; right: 12px; padding: 6px 12px; border-radius: 8px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
.status-overlay.available { background: #34c759; color: white; }
.status-overlay.upcoming { background: #ff9500; color: white; }
.status-overlay.sold_out { background: #ff3b30; color: white; }
.status-overlay.not_available { background: #8e8e93; color: white; }

.card-body { padding: 1.25rem; }
.card-body h3 { font-size: 1.15rem; font-weight: 700; margin-bottom: 4px; color: #1c1c1e; }
.location { color: #6c6c70; font-size: 0.9rem; margin-bottom: 1rem; }

.match-info { background: #f9f9fb; padding: 12px; border-radius: 10px; }
.info-item { display: flex; justify-content: space-between; align-items: center; }
.info-item + .info-item { margin-top: 8px; padding-top: 8px; border-top: 1px solid #e5e5ea; }
.info-item .label { font-size: 0.8rem; color: #8e8e93; text-transform: uppercase; letter-spacing: 0.3px; }
.info-item .value { font-size: 0.9rem; font-weight: 600; color: #1c1c1e; }
.info-item .sale-date { color: #007AFF; }

.card-footer { padding: 0 1.25rem 1.25rem; }

.schedule-btn { width: 100%; padding: 14px; background: #1c1c1e; color: white; border: none; border-radius: 12px; font-weight: 600; cursor: pointer; transition: 0.2s; }
.schedule-btn:hover { background: #3a3a3c; }
.schedule-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.buy-btn { display: block; width: 100%; padding: 14px; background: #34c759; color: white; border: none; border-radius: 12px; font-weight: 600; text-align: center; text-decoration: none; transition: 0.2s; }
.buy-btn:hover { background: #2db84d; }

.scheduled-badge { text-align: center; padding: 14px; background: rgba(52, 199, 89, 0.1); color: #34c759; border-radius: 12px; font-weight: 600; }

/* Loading & Empty States */
.loading-state, .empty-state, .error-state { text-align: center; padding: 4rem 2rem; color: #8e8e93; }
.empty-icon, .error-icon { font-size: 3rem; margin-bottom: 1rem; opacity: 0.5; }
.spinner { width: 40px; height: 40px; border: 3px solid #e5e5ea; border-top-color: #1c1c1e; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1rem; }
@keyframes spin { to { transform: rotate(360deg); } }

.retry-btn { margin-top: 1rem; padding: 10px 20px; background: #1c1c1e; color: white; border: none; border-radius: 8px; cursor: pointer; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; backdrop-filter: blur(5px); z-index: 100; }
.modal { background: white; padding: 2rem; border-radius: 20px; width: 100%; max-width: 400px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); }
.modal h3 { font-size: 1.4rem; font-weight: 700; margin-bottom: 0.25rem; }
.modal-subtitle { color: #8e8e93; margin-bottom: 1.5rem; }

.form-group { margin-bottom: 1.25rem; }
.form-group label { display: block; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.5rem; color: #1c1c1e; }
.form-group input { width: 100%; padding: 12px; border: 1px solid #e5e5ea; border-radius: 10px; font-size: 1rem; }

.sale-info { background: #f2f2f7; padding: 12px; border-radius: 10px; display: flex; justify-content: space-between; margin-bottom: 1.5rem; }
.sale-info .label { color: #8e8e93; font-size: 0.85rem; }
.sale-info .value { font-weight: 600; color: #007AFF; }

.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; }
.cancel-btn { background: #f2f2f7; color: #1c1c1e; border: none; padding: 12px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; }
.confirm-btn { background: #1c1c1e; color: white; border: none; padding: 12px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; }
.confirm-btn:disabled { opacity: 0.6; }

.cancel-schedule-btn {
  width: 100%;
  margin-top: 8px;
  padding: 12px;
  background: #ff3b30;
  color: white;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: 0.2s;
}
.cancel-schedule-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
