<template>
  <div class="logs-view">
    <div class="toolbar">
      <div class="log-stats">
        <span class="count">{{ logs.length }} entries</span>
      </div>
      <div class="toolbar-actions">
        <select v-model="filterTask" class="filter-select">
          <option :value="null">All Tasks</option>
          <option v-for="id in taskIds" :key="id" :value="id">Task #{{ id }}</option>
        </select>
        <select v-model="filterLevel" class="filter-select">
          <option value="">All Levels</option>
          <option value="info">Info</option>
          <option value="success">Success</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
        </select>
        <button @click="clearLogs()" class="clear-btn">Clear</button>
      </div>
    </div>

    <div v-if="filteredLogs.length === 0" class="empty-state">
      <div class="empty-icon">📋</div>
      <h3>No Logs</h3>
      <p>Logs appear here in real-time when tasks are running.</p>
    </div>

    <div v-else class="log-list">
      <div v-for="(log, i) in filteredLogs" :key="i" class="log-entry" :class="log.level">
        <div class="log-meta">
          <span class="log-time">{{ formatTime(log.timestamp) }}</span>
          <span class="log-task">T{{ log.task_id }}</span>
          <span class="log-level" :class="log.level">{{ log.level }}</span>
        </div>
        <div class="log-message">{{ log.message }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useLogStore } from '../stores/logs';

const { logs, addLog, clear: clearLogs } = useLogStore();
const filterTask = ref(null);
const filterLevel = ref('');

const taskIds = computed(() => {
  const ids = new Set(logs.value.map(l => l.task_id));
  return [...ids].sort((a, b) => a - b);
});

const filteredLogs = computed(() => {
  return logs.value.filter(l => {
    if (filterTask.value !== null && l.task_id !== filterTask.value) return false;
    if (filterLevel.value && l.level !== filterLevel.value) return false;
    return true;
  });
});

const formatTime = (ts) => {
  if (!ts) return '';
  try {
    const d = new Date(ts.endsWith('Z') ? ts : ts + 'Z');
    return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch { return ts; }
};
</script>

<style scoped>
.logs-view { padding: 0; }

.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;
}
.toolbar-actions { display: flex; gap: 0.5rem; align-items: center; }
.log-stats .count { color: var(--text-tertiary); font-size: 0.85rem; }
.filter-select {
  padding: 8px 12px; border: 1px solid var(--border-light); border-radius: 8px;
  font-size: 0.85rem; background: var(--input-bg); color: var(--text-primary);
}
.clear-btn {
  padding: 8px 16px; border: 1px solid var(--border-light); border-radius: 8px;
  background: none; color: var(--text-secondary); cursor: pointer; font-size: 0.85rem;
}
.clear-btn:hover { background: var(--hover-bg); }

.log-list {
  background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border-light);
  overflow: hidden; max-height: calc(100vh - 220px); overflow-y: auto;
}

.log-entry {
  padding: 8px 16px; border-bottom: 1px solid var(--border-light);
  font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.82rem;
}
.log-entry:last-child { border-bottom: none; }
.log-entry.error { background: rgba(255,59,48,0.05); }
.log-entry.success { background: rgba(52,199,89,0.05); }
.log-entry.warning { background: rgba(255,149,0,0.05); }

.log-meta { display: flex; gap: 8px; align-items: center; margin-bottom: 2px; }
.log-time { color: var(--text-tertiary); font-size: 0.75rem; }
.log-task {
  background: var(--hover-bg); padding: 1px 6px; border-radius: 4px;
  font-size: 0.7rem; font-weight: 600; color: var(--text-secondary);
}
.log-level {
  padding: 1px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
}
.log-level.info { background: rgba(0,122,255,0.1); color: #007AFF; }
.log-level.success { background: rgba(52,199,89,0.15); color: #34c759; }
.log-level.warning { background: rgba(255,149,0,0.15); color: #ff9500; }
.log-level.error { background: rgba(255,59,48,0.15); color: #ff3b30; }

.log-message { color: var(--text-primary); word-break: break-word; line-height: 1.4; }

.empty-state { text-align: center; padding: 4rem; color: var(--text-tertiary); }
.empty-icon { font-size: 3rem; margin-bottom: 1rem; }

@media (max-width: 768px) {
  .toolbar { flex-direction: column; align-items: stretch; }
  .log-entry { padding: 6px 12px; font-size: 0.78rem; }
}
</style>
