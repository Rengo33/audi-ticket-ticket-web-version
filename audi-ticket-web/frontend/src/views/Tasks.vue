<template>
  <div>
    <div class="view-head">
      <div>
        <div class="eyebrow">MONITORING</div>
        <h1 class="view-title">Tasks</h1>
      </div>
      <button @click="showModal = true" class="btn btn-primary">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        <span>New task</span>
      </button>
    </div>

    <!-- Scheduled -->
    <section v-if="scheduledTasks.length > 0" class="section">
      <div class="section-head">
        <span class="eyebrow">Scheduled · {{ scheduledTasks.length }}</span>
      </div>
      <div class="cards">
        <article v-for="st in scheduledTasks" :key="'s-' + st.id" class="task-card is-scheduled">
          <div class="task-top">
            <span class="badge" :class="st.status === 'triggered' ? 'badge-triggered' : 'badge-scheduled'">
              <span v-if="st.status === 'scheduled'" class="live-dot"></span>
              {{ st.status }}
            </span>
            <span class="task-tag mono">{{ st.game_title }}</span>
          </div>
          <h3 class="task-title">{{ getDisplayName(st.product_url) }}</h3>
          <div class="task-stats">
            <div class="stat">
              <div class="stat-label mono">QTY · THR · CAT</div>
              <div class="stat-value mono">{{ st.quantity }} · {{ st.num_threads }} · {{ priceCategoryLabel(st.price_category) }}</div>
            </div>
            <div class="stat">
              <div class="stat-label mono">Fires</div>
              <div class="stat-value mono">{{ formatScheduledDate(st.scheduled_date) }}</div>
            </div>
          </div>
          <div class="task-actions">
            <button @click="cancelScheduled(st.id)" class="icon-btn is-danger" :disabled="cancellingId === st.id" title="Cancel">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
            </button>
          </div>
        </article>
      </div>
    </section>

    <!-- Active -->
    <section class="section">
      <div class="section-head">
        <span class="eyebrow">Active · {{ taskStore.tasks.length }}</span>
      </div>
      <div v-if="taskStore.tasks.length === 0" class="empty">
        <div class="empty-mark">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10M7 13h10M7 17h6"/></svg>
        </div>
        <h3>No active tasks</h3>
        <p>Create one from a product URL or schedule one from the Games tab.</p>
      </div>
      <div v-else class="cards">
        <article v-for="task in taskStore.tasks" :key="task.id" class="task-card" :class="'is-' + task.status">
          <div class="task-top">
            <span class="badge" :class="'badge-' + task.status">
              <span v-if="task.status === 'running'" class="live-dot"></span>
              {{ task.status }}
            </span>
            <span class="task-tag mono">#{{ task.id }}</span>
          </div>

          <h3 class="task-title">{{ getDisplayName(task.product_url) }}</h3>

          <div class="task-stats">
            <div class="stat">
              <div class="stat-label mono">QTY · THR · CAT</div>
              <div class="stat-value mono">{{ task.quantity }} · {{ task.num_threads }} · {{ priceCategoryLabel(task.price_category) }}</div>
            </div>
            <div class="stat">
              <div class="stat-label mono">Scans</div>
              <div class="stat-value mono tnum">{{ (task.scan_count || 0).toLocaleString() }}</div>
            </div>
          </div>

          <div class="task-status-row" :class="{
            'is-avail':   (task.tickets_available || 0) > 0,
            'is-waiting': (task.tickets_available || 0) <= 0
          }">
            <span class="status-dot"></span>
            <span>
              {{ (task.tickets_available || 0) > 0
                  ? `${task.tickets_available} tickets available`
                  : 'Waiting for release' }}
            </span>
          </div>

          <div class="task-actions">
            <button
              v-if="!['running','success','waiting'].includes(task.status)"
              @click="taskStore.startTask(task.id)"
              class="icon-btn is-ok"
              title="Start"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20 6 4"/></svg>
            </button>
            <button
              v-if="['running','success','waiting'].includes(task.status)"
              @click="taskStore.stopTask(task.id)"
              class="icon-btn is-danger"
              title="Stop"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="1"/></svg>
            </button>
            <button
              v-if="!['running','success','waiting'].includes(task.status)"
              @click="taskStore.deleteTask(task.id)"
              class="icon-btn is-danger"
              title="Delete"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
            </button>
          </div>
        </article>
      </div>
    </section>

    <!-- Create Modal -->
    <transition name="fade">
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <header class="modal-header">
          <div>
            <div class="modal-title">Create task</div>
            <div class="modal-sub">Monitor a product URL and auto-cart on release.</div>
          </div>
          <button @click="showModal = false" class="icon-btn" aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </header>

        <div class="modal-body">
          <div class="form-section">
            <div class="form-section-title">Target</div>
            <div class="field">
              <label class="field-label">Product URL</label>
              <input v-model="newTask.url" placeholder="https://audidefuehrungen2.regiondo.de/...">
            </div>
            <div class="field-row">
              <div class="field">
                <label class="field-label">Quantity</label>
                <input v-model="newTask.quantity" type="number" min="1" max="4">
              </div>
              <div class="field">
                <label class="field-label">Threads</label>
                <input v-model="newTask.num_threads" type="number" min="1" max="10">
              </div>
            </div>
            <div class="field">
              <label class="field-label">Price category</label>
              <select v-model="newTask.price_category">
                <option v-for="cat in PRICE_CATEGORIES" :key="cat.value" :value="cat.value">{{ cat.label }}</option>
              </select>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Auto-checkout</div>
            <label class="check-row">
              <input type="checkbox" v-model="newTask.auto_checkout">
              <span>Run ACO when tickets are carted</span>
            </label>
            <div v-if="newTask.auto_checkout" class="profiles-list">
              <div class="field-label" style="margin-top: 10px;">Billing profiles <span class="field-hint">(round-robin)</span></div>
              <label v-for="p in billingProfiles" :key="p.id" class="check-row">
                <input type="checkbox" :value="p.id" v-model="newTask.billing_profile_ids">
                <span class="profile-name">{{ p.name }}</span>
                <span v-if="p.card_last4" class="mono profile-card">•••• {{ p.card_last4 }}</span>
              </label>
              <div v-if="billingProfiles.length === 0" class="profiles-empty mono">No profiles — add one in Billing.</div>
            </div>
          </div>
        </div>

        <footer class="modal-footer">
          <button @click="showModal = false" class="btn btn-ghost">Cancel</button>
          <button @click="createTask" class="btn btn-primary" :disabled="!newTask.url">Create task</button>
        </footer>
      </div>
    </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useTaskStore } from '../stores/tasks';
import { api } from '../stores/api';
import { PRICE_CATEGORIES, priceCategoryLabel } from '../constants';

const taskStore = useTaskStore();
const showModal = ref(false);
const newTask = ref({ url: '', quantity: 2, num_threads: 2, price_category: 0, auto_checkout: false, billing_profile_ids: [] });
const billingProfiles = ref([]);
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
    const d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z');
    return d.toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
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
    price_category: parseInt(newTask.value.price_category),
    auto_checkout: newTask.value.auto_checkout,
    billing_profile_id: newTask.value.auto_checkout ? newTask.value.billing_profile_ids.join(',') : null
  });
  showModal.value = false;
  newTask.value = { url: '', quantity: 2, num_threads: 2, price_category: 0, auto_checkout: false, billing_profile_ids: [] };
};

const fetchBillingProfiles = async () => {
  try { billingProfiles.value = await api.get('/api/billing/profiles'); } catch { /* ignore */ }
};

onMounted(() => {
  if (taskStore.tasks.length === 0) taskStore.fetchTasks();
  fetchScheduled();
  fetchBillingProfiles();
});
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

.section { margin-bottom: 2rem; }
.section-head { margin-bottom: 0.75rem; display: flex; align-items: center; }

.cards {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
@media (min-width: 640px) { .cards { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1100px) { .cards { grid-template-columns: repeat(3, 1fr); } }

/* Task card */
.task-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 14px;
  display: flex; flex-direction: column;
  gap: 12px;
  position: relative;
  overflow: hidden;
  transition: border-color 0.15s, transform 0.15s;
}
.task-card::before {
  content: "";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--line);
  transition: background 0.2s;
}
.task-card.is-running::before   { background: var(--signal); }
.task-card.is-success::before   { background: var(--ok); }
.task-card.is-failed::before    { background: var(--bad); }
.task-card.is-pending::before   { background: var(--warn); }
.task-card.is-waiting::before   { background: var(--warn); }
.task-card.is-scheduled::before { background: var(--ink); }
.task-card:hover { border-color: color-mix(in oklab, var(--ink) 30%, var(--line)); }

.task-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.task-tag {
  font-size: 0.75rem;
  color: var(--ink-3);
  font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 60%;
}

.task-title {
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.3;
  color: var(--ink);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 2.6em;
}

.task-stats {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px 16px;
  padding: 10px 12px;
  background: var(--surface-2);
  border-radius: var(--radius);
  border: 1px solid var(--line-soft);
}
.stat { min-width: 0; }
.stat-label {
  font-size: 0.625rem; font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-4);
  margin-bottom: 2px;
}
.stat-value {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.task-status-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius);
  font-size: 0.8125rem;
  font-weight: 600;
  font-family: var(--font-mono);
}
.task-status-row.is-avail {
  background: var(--ok-soft);
  color: var(--ok);
}
.task-status-row.is-waiting {
  background: var(--warn-soft);
  color: var(--warn);
}
.status-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: currentColor;
}
.is-avail .status-dot { animation: live-pulse 1.6s infinite; }

.task-actions {
  display: flex; gap: 6px;
  justify-content: flex-end;
}

/* Modal specifics */
.field-hint { color: var(--ink-4); font-weight: 400; margin-left: 4px; text-transform: none; letter-spacing: 0; }
.profiles-list { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
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

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
