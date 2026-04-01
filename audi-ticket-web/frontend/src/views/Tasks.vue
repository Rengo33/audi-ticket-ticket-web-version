<template>
  <div class="tasks-view">
    <div class="toolbar">
      <button @click="showModal = true" class="primary-btn">+ New Task</button>
    </div>

    <!-- Scheduled Tasks -->
    <div v-if="scheduledTasks.length > 0" class="scheduled-section">
      <h3 class="section-title">Scheduled</h3>
      <div class="tasks-grid">
        <div v-for="st in scheduledTasks" :key="'s-' + st.id" class="task-card scheduled-card">
          <div class="card-header">
            <div class="status-badge scheduled">
              {{ st.status === 'triggered' ? 'triggered' : 'scheduled' }}
              <span v-if="st.status === 'scheduled'" class="pulse scheduled-pulse"></span>
            </div>
            <span class="task-id">⚽ {{ st.game_title }}</span>
          </div>
          <div class="card-body">
            <h3>{{ getDisplayName(st.product_url) }}</h3>
            <div class="stats-grid">
              <div class="stat">
                <span class="label">Config</span>
                <span class="value">{{ st.quantity }}tix / {{ st.num_threads }}thr / {{ priceCategoryLabel(st.price_category) }}</span>
              </div>
              <div class="stat">
                <span class="label">Starts at</span>
                <span class="value">{{ formatScheduledDate(st.scheduled_date) }}</span>
              </div>
            </div>
          </div>
          <div class="card-footer">
            <button @click="cancelScheduled(st.id)" class="icon-btn delete" :disabled="cancellingId === st.id">
              🗑
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Active Tasks -->
    <h3 v-if="scheduledTasks.length > 0" class="section-title">Tasks</h3>
    <div class="tasks-grid">
      <div v-for="task in taskStore.tasks" :key="task.id" class="task-card">
        <div class="card-header">
          <div class="status-badge" :class="task.status">
            {{ task.status }}
            <span v-if="task.status === 'running'" class="pulse"></span>
          </div>
          <span class="task-id">#{{ task.id }}</span>
        </div>

        <div class="card-body">
          <h3>{{ getDisplayName(task.product_url) }}</h3>

          <div class="stats-grid">
            <div class="stat">
              <span class="label">Config</span>
              <span class="value">{{ task.quantity }}tix / {{ task.num_threads }}thr / {{ priceCategoryLabel(task.price_category) }}</span>
            </div>
            <div class="stat">
              <span class="label">Scans</span>
              <span class="value">{{ task.scan_count || 0 }}</span>
            </div>
            <div class="stat full-width">
              <span class="label">Status</span>
              <span class="value status-text" :class="{
                'avail': (task.tickets_available || 0) > 0,
                'waiting': (task.tickets_available || 0) <= 0
              }">
                {{ (task.tickets_available || 0) > 0 ? `${task.tickets_available} Tickets Available` : 'Waiting for Release' }}
              </span>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <button v-if="task.status !== 'running' && task.status !== 'success' && task.status !== 'waiting'" @click="taskStore.startTask(task.id)" class="icon-btn play">
            ▶
          </button>
          <button v-if="task.status === 'running' || task.status === 'success' || task.status === 'waiting'" @click="taskStore.stopTask(task.id)" class="icon-btn stop">
            ⏹
          </button>
          <button v-if="task.status !== 'running' && task.status !== 'success' && task.status !== 'waiting'" @click="taskStore.deleteTask(task.id)" class="icon-btn delete">
            🗑
          </button>
        </div>
      </div>
    </div>

    <!-- Simple Modal for Creation -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <h3>Create Task</h3>
        <div class="form-group">
            <label>Product URL</label>
            <input v-model="newTask.url" placeholder="https://..." class="w-full">
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>Quantity</label>
                <input v-model="newTask.quantity" type="number" min="1">
            </div>
            <div class="form-group">
                <label>Threads</label>
                <input v-model="newTask.num_threads" type="number" min="1">
            </div>
        </div>
        <div class="form-group">
            <label>Price Category</label>
            <select v-model="newTask.price_category" class="w-full">
                <option v-for="cat in PRICE_CATEGORIES" :key="cat.value" :value="cat.value">{{ cat.label }}</option>
            </select>
        </div>

        <div class="modal-actions">
            <button @click="showModal = false" class="cancel-btn">Cancel</button>
            <button @click="createTask" class="create-btn">Create Task</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useTaskStore } from '../stores/tasks';
import { api } from '../stores/api';
import { PRICE_CATEGORIES, priceCategoryLabel } from '../constants';

const taskStore = useTaskStore();
const showModal = ref(false);
const newTask = ref({ url: '', quantity: 2, num_threads: 2, price_category: 0 });
const scheduledTasks = ref([]);
const cancellingId = ref(null);

const getDisplayName = (url) => {
    try {
        const parts = url.split('/');
        return parts[parts.length - 1].replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    } catch { return url; }
};

const formatScheduledDate = (dateStr) => {
    try {
        // Backend stores UTC without Z suffix — append it so browser converts to local time
        const d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z');
        return d.toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return dateStr; }
};

const fetchScheduled = async () => {
    try {
        const response = await api.get('/api/games/scheduled');
        scheduledTasks.value = (Array.isArray(response) ? response : []).filter(
            s => s.status === 'scheduled' || s.status === 'triggered'
        );
    } catch { /* ignore */ }
};

const cancelScheduled = async (id) => {
    cancellingId.value = id;
    try {
        await api.delete(`/api/games/scheduled/${id}`);
        scheduledTasks.value = scheduledTasks.value.filter(s => s.id !== id);
    } catch (e) {
        alert('Failed to cancel: ' + (e.message || 'Unknown error'));
    } finally {
        cancellingId.value = null;
    }
};

const createTask = async () => {
    if (!newTask.value.url) return;

    await taskStore.createTask({
        product_url: newTask.value.url,
        quantity: parseInt(newTask.value.quantity),
        num_threads: parseInt(newTask.value.num_threads),
        price_category: parseInt(newTask.value.price_category)
    });

    showModal.value = false;
    newTask.value = { url: '', quantity: 2, num_threads: 2, price_category: 0 };
};

onMounted(() => {
    taskStore.fetchTasks();
    fetchScheduled();
});
</script>

<style scoped>
.tasks-view { padding: 0; }

.toolbar { margin-bottom: 2rem; display: flex; justify-content: flex-end; }
.primary-btn { background: var(--btn-primary-bg); color: var(--btn-primary-text); padding: 12px 24px; border-radius: 12px; font-weight: 600; cursor: pointer; border: none; transition: 0.2s; }
.primary-btn:hover { background: var(--btn-primary-hover); }

.tasks-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1.5rem; }

.task-card { background: var(--card-bg); border-radius: 16px; padding: 1.5rem; border: 1px solid var(--border-light); transition: transform 0.2s, box-shadow 0.2s; }
.task-card:hover { transform: translateY(-2px); box-shadow: 0 10px 30px var(--card-shadow); }

.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }

.status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 8px; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; }
.status-badge.running { background: rgba(0, 122, 255, 0.12); color: #007AFF; }
.status-badge.success { background: rgba(52, 199, 89, 0.12); color: #34c759; }
.status-badge.failed { background: rgba(255, 59, 48, 0.12); color: #ff3b30; }
.status-badge.pending { background: rgba(255, 149, 0, 0.12); color: #ff9500; }
.status-badge.waiting { background: rgba(255, 149, 0, 0.12); color: #ff9500; }
.status-badge.scheduled { background: rgba(88, 86, 214, 0.12); color: var(--purple); }
.status-badge.triggered { background: rgba(0, 122, 255, 0.12); color: #007AFF; }
.status-badge.stopped { background: rgba(142, 142, 147, 0.12); color: var(--text-tertiary); }

.section-title { font-size: 1.1rem; font-weight: 700; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 1rem; }
.scheduled-section { margin-bottom: 2rem; }
.scheduled-card { border-color: #d1d1f7; }
.scheduled-pulse { background: var(--purple); }

.pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-blue); animation: pulse-dot 1.5s infinite; }
@keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.task-id { font-size: 0.85rem; color: var(--text-tertiary); font-weight: 600; }

.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.stat { background: var(--stat-bg); padding: 10px 12px; border-radius: 10px; }
.stat.full-width { grid-column: 1 / -1; }
.stat .label { font-size: 0.75rem; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.3px; display: block; margin-bottom: 2px; }
.stat .value { font-size: 1rem; font-weight: 700; color: var(--text-primary); }
.stat .status-text.avail { color: var(--success); }
.stat .status-text.waiting { color: var(--warning); }

.card-footer { display: flex; gap: 0.5rem; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--hover-bg); }

.icon-btn { width: 44px; height: 44px; border-radius: 12px; border: none; font-size: 1.1rem; cursor: pointer; transition: 0.2s; display: flex; align-items: center; justify-content: center; }
.icon-btn.play { background: rgba(52, 199, 89, 0.12); color: #34c759; }
.icon-btn.play:hover { background: rgba(52, 199, 89, 0.2); }
.icon-btn.stop { background: rgba(255, 59, 48, 0.12); color: #ff3b30; }
.icon-btn.stop:hover { background: rgba(255, 59, 48, 0.2); }
.icon-btn.delete { background: rgba(142, 142, 147, 0.08); color: var(--text-tertiary); }
.icon-btn.delete:hover { background: rgba(142, 142, 147, 0.15); }

.card-body h3 {
  font-size: 1.22rem;
  font-weight: 800;
  margin-bottom: 1rem;
  line-height: 1.4;
  color: var(--text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 3em;
}

.form-group label {
  display: block;
  font-size: 1.08rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
  letter-spacing: 0.01em;
}
.form-group input, .form-group select {
  width: 100%;
  padding: 15px;
  border: 2px solid var(--border);
  border-radius: 10px;
  font-size: 1.12rem;
  color: var(--text-primary);
  background: var(--input-bg);
  font-weight: 600;
}

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: var(--modal-overlay); display: flex; align-items: center; justify-content: center; backdrop-filter: blur(5px); z-index: 100; }
.modal { background: var(--card-bg); padding: 2rem; border-radius: 20px; width: 100%; max-width: 500px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); }
.modal h3 { font-size: 1.5rem; font-weight: 700; margin-bottom: 1.5rem; }

.form-group { margin-bottom: 1rem; }
.form-group label { display: block; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.5rem; }
.form-group input { width: 100%; padding: 12px; border: 1px solid var(--border-light); border-radius: 10px; font-size: 1rem; }
.form-row { display: flex; gap: 1rem; }
.form-row .form-group { flex: 1; }

.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; }
.cancel-btn { background: var(--hover-bg); color: var(--text-primary); border: none; padding: 12px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; }
.create-btn { background: var(--btn-primary-bg); color: var(--btn-primary-text); border: none; padding: 12px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; }

@media (max-width: 768px) {
  .tasks-grid { grid-template-columns: 1fr; }
  .task-card { padding: 1rem; }
  .modal { max-width: 95vw; padding: 1.5rem; }
}
</style>
