<template>
  <div>
    <div class="view-head">
      <div>
        <div class="eyebrow">REAL-TIME STREAM</div>
        <h1 class="view-title">Logs <span class="count mono">{{ filteredLogs.length }}</span></h1>
      </div>
      <button @click="clearLogs()" class="btn btn-ghost" title="Clear client-side log buffer">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        <span>Clear</span>
      </button>
    </div>

    <div class="log-filters">
      <div class="chip-group" role="tablist">
        <button
          class="chip mono" :class="{ 'is-active': filterTask === null }"
          @click="filterTask = null"
        >All</button>
        <button
          v-for="id in taskIds" :key="id"
          class="chip mono" :class="{ 'is-active': filterTask === id }"
          @click="filterTask = id"
        >#{{ id }}</button>
      </div>
      <div class="chip-group" role="tablist">
        <button
          v-for="lvl in ['', 'info', 'success', 'warning', 'error']" :key="lvl"
          class="chip mono" :class="[{ 'is-active': filterLevel === lvl }, 'lvl-' + (lvl || 'all')]"
          @click="filterLevel = lvl"
        >{{ lvl || 'all' }}</button>
      </div>
    </div>

    <div v-if="filteredLogs.length === 0" class="empty">
      <div class="empty-mark">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 5h16M4 10h16M4 15h10M4 20h16"/></svg>
      </div>
      <h3>No logs yet</h3>
      <p>Logs stream here in real-time when tasks are running.</p>
    </div>

    <div v-else class="log-stream">
      <div v-for="(log, i) in filteredLogs" :key="i" class="log-row" :class="'lvl-' + log.level">
        <div class="log-gutter">
          <span class="log-level mono" :class="'lvl-' + log.level">{{ (log.level || 'info').slice(0,1).toUpperCase() }}</span>
        </div>
        <div class="log-body">
          <div class="log-meta mono">
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
            <span class="log-task">T{{ log.task_id }}</span>
          </div>
          <div class="log-message">{{ log.message }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useLogStore } from '../stores/logs';

const { logs, clear: clearLogs } = useLogStore();
const filterTask = ref(null);
const filterLevel = ref('');

const taskIds = computed(() => {
  const ids = new Set(logs.value.map(l => l.task_id));
  return [...ids].sort((a, b) => a - b);
});

const filteredLogs = computed(() => logs.value.filter(l => {
  if (filterTask.value !== null && l.task_id !== filterTask.value) return false;
  if (filterLevel.value && l.level !== filterLevel.value) return false;
  return true;
}));

const formatTime = (ts) => {
  if (!ts) return '';
  try {
    const d = new Date(ts.endsWith('Z') ? ts : ts + 'Z');
    return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch { return ts; }
};
</script>

<style scoped>
.view-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.view-title {
  font-size: clamp(1.5rem, 4vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin-top: 4px;
  display: flex; align-items: baseline; gap: 10px;
}
.count {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--ink-4);
}

.log-filters {
  display: flex; flex-direction: column; gap: 8px;
  margin-bottom: 1rem;
}
.chip-group {
  display: flex; gap: 6px;
  overflow-x: auto;
  scrollbar-width: none;
  padding-bottom: 2px;
}
.chip-group::-webkit-scrollbar { display: none; }

.chip {
  flex-shrink: 0;
  padding: 6px 12px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
  color: var(--ink-3);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  -webkit-tap-highlight-color: transparent;
}
.chip:hover { color: var(--ink); border-color: var(--ink-3); }
.chip.is-active { background: var(--ink); color: var(--bg); border-color: var(--ink); }
.chip.lvl-error.is-active { background: var(--bad); border-color: var(--bad); color: white; }
.chip.lvl-success.is-active { background: var(--ok); border-color: var(--ok); color: white; }
.chip.lvl-warning.is-active { background: var(--warn); border-color: var(--warn); color: white; }
.chip.lvl-info.is-active { background: var(--info); border-color: var(--info); color: white; }

.log-stream {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  overflow: hidden;
  font-family: var(--font-mono);
  max-height: calc(100vh - 280px);
  overflow-y: auto;
}

.log-row {
  display: grid;
  grid-template-columns: 36px 1fr;
  border-bottom: 1px solid var(--line-soft);
  padding: 8px 12px 8px 0;
}
.log-row:last-child { border-bottom: none; }
.log-row.lvl-error { background: color-mix(in oklab, var(--bad) 6%, transparent); }
.log-row.lvl-success { background: color-mix(in oklab, var(--ok) 5%, transparent); }
.log-row.lvl-warning { background: color-mix(in oklab, var(--warn) 5%, transparent); }

.log-gutter {
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 2px;
}
.log-level {
  display: inline-flex; align-items: center; justify-content: center;
  width: 20px; height: 20px;
  border-radius: 4px;
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0;
}
.log-level.lvl-info { background: var(--info-soft); color: var(--info); }
.log-level.lvl-success { background: var(--ok-soft); color: var(--ok); }
.log-level.lvl-warning { background: var(--warn-soft); color: var(--warn); }
.log-level.lvl-error { background: var(--bad-soft); color: var(--bad); }

.log-body { min-width: 0; }
.log-meta {
  display: flex; gap: 10px;
  font-size: 0.6875rem;
  color: var(--ink-4);
  margin-bottom: 1px;
}
.log-task {
  color: var(--ink-3);
  font-weight: 600;
}
.log-message {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--ink-2);
  word-break: break-word;
}

@media (max-width: 600px) {
  .log-stream { max-height: calc(100vh - 320px); }
  .log-row { padding-right: 10px; }
  .log-message { font-size: 0.6875rem; }
}
</style>
