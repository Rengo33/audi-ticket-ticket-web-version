<template>
  <div>
    <div class="view-head">
      <div>
        <div class="eyebrow">AUTO-DETECT RELEASES</div>
        <h1 class="view-title">Detector</h1>
      </div>
      <button
        class="btn"
        :class="status.running ? 'btn-danger' : 'btn-primary'"
        :disabled="busy"
        @click="status.running ? stop() : start()"
      >
        {{ status.running ? 'Stop' : 'Start' }}
      </button>
    </div>

    <p class="lede">
      Watches new product IDs as soon as Audi creates them (before release). A matching
      game gets its task immediately; the task carts the moment the game goes live.
      First scan after Start only seeds the baseline.
    </p>

    <!-- status -->
    <div class="card">
      <div class="status-row">
        <span class="dot" :class="status.running ? 'on' : 'off'"></span>
        <strong>{{ status.running ? 'Running' : (status.active ? 'Active (restarting…)' : 'Stopped') }}</strong>
      </div>
      <dl class="stat-grid">
        <div><dt>Scans</dt><dd class="mono">{{ status.scan_count }}</dd></div>
        <div><dt>Highest ID</dt><dd class="mono">{{ status.frontier_id || '—' }}</dd></div>
        <div><dt>Last scan</dt><dd class="mono">{{ fmt(status.last_scan_at) }}</dd></div>
        <div><dt>Last new found</dt><dd class="mono">{{ fmt(status.last_new_found_at) }}</dd></div>
      </dl>
      <p v-if="status.error_message" class="err">{{ status.error_message }}</p>
    </div>

    <!-- config -->
    <div class="card">
      <h3 class="card-title">Configuration</h3>
      <div class="form-grid">
        <label>Keyword filter
          <input v-model="cfg.keyword" placeholder="fc-bayern" />
          <small>Combine terms with <code>+</code> (AND), e.g. <code>dortmund+ingolstadt</code>. Empty = every new event.</small>
        </label>
        <label>Poll interval (s)
          <input v-model.number="cfg.poll_interval" type="number" min="150" step="1" />
        </label>
        <label>Quantity
          <input v-model.number="cfg.quantity" type="number" min="1" max="4" />
        </label>
        <label>Price category (index)
          <input v-model.number="cfg.price_category" type="number" min="0" />
        </label>
        <label>Threads
          <input v-model.number="cfg.num_threads" type="number" min="1" max="10" />
        </label>
        <label>Billing profile (ACO)
          <select v-model="cfg.billing_profile_id">
            <option :value="null">— none —</option>
            <option v-for="p in profiles" :key="p.id" :value="String(p.id)">{{ p.name }}</option>
          </select>
        </label>
        <label class="checkbox">
          <input v-model="cfg.auto_checkout" type="checkbox" />
          <span>Auto Checkout (ACO) on cart success</span>
        </label>
        <label class="checkbox">
          <input v-model="cfg.reseed" type="checkbox" />
          <span>Reseed baseline on start (forget seen products)</span>
        </label>
      </div>
      <p class="hint">Changes apply when you press Start. Start while running to re-apply config.</p>
    </div>

    <!-- Audi products found before release (booking-widget scan) -->
    <div class="card">
      <h3 class="card-title">Audi products seen before release</h3>
      <div v-if="!status.launched || Object.keys(status.launched).length === 0" class="muted">None yet.</div>
      <ul v-else class="events">
        <li v-for="(name, id) in status.launched" :key="id">
          <span class="mono time">#{{ id }}</span>
          <span>{{ name }}</span>
        </li>
      </ul>
    </div>

    <!-- recent detections -->
    <div class="card">
      <h3 class="card-title">Recent detections</h3>
      <div v-if="!status.events_log || status.events_log.length === 0" class="muted">Nothing detected yet.</div>
      <ul v-else class="events">
        <li v-for="(e, i) in status.events_log" :key="i">
          <span class="mono time">{{ fmt(e.at) }}</span>
          <a :href="e.url" target="_blank" rel="noopener">{{ e.name || shortUrl(e.url) }}</a>
          <span v-if="e.task_id" class="tag">task #{{ e.task_id }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { api } from '../stores/api'

const status = ref({ running: false, active: false, scan_count: 0, events_log: [], frontier_id: null, launched: {} })
const profiles = ref([])
const busy = ref(false)
let timer = null

const cfg = reactive({
  keyword: 'fc-bayern',
  poll_interval: 150,
  quantity: 1,
  price_category: 0,
  num_threads: 1,
  billing_profile_id: null,
  auto_checkout: false,
  reseed: false,
})

function fmt(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z')
  return d.toLocaleString()
}
function shortUrl(u) { try { return new URL(u).pathname.replace(/^\//, '') } catch { return u } }

async function load() {
  try {
    const s = await api.get('/api/detector')
    status.value = s
    // hydrate the form from saved config (but don't clobber while user edits — only on first load)
    if (!loaded) {
      cfg.keyword = s.keyword
      cfg.poll_interval = s.poll_interval
      cfg.quantity = s.quantity
      cfg.price_category = s.price_category
      cfg.num_threads = s.num_threads
      cfg.billing_profile_id = s.billing_profile_id
      cfg.auto_checkout = s.auto_checkout
      loaded = true
    }
  } catch { /* ignore transient */ }
}
let loaded = false

async function start() {
  busy.value = true
  try {
    status.value = await api.post('/api/detector/start', { ...cfg })
    cfg.reseed = false
  } finally { busy.value = false }
}
async function stop() {
  busy.value = true
  try { status.value = await api.post('/api/detector/stop', {}) } finally { busy.value = false }
}

onMounted(async () => {
  try { profiles.value = await api.get('/api/billing/profiles') } catch { /* ignore */ }
  await load()
  timer = setInterval(load, 4000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
/* Match the house style: shared design tokens, same title/card language as the
   other views — no hardcoded hex. */
.view-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
}
.view-title {
  font-size: clamp(1.5rem, 4vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin-top: 4px;
}
.lede { color: var(--ink-3); max-width: 62ch; margin: 0 0 1.25rem; font-size: 0.875rem; line-height: 1.5; }
.card { margin-bottom: 1rem; }
.card-title { margin: 0 0 1rem; font-size: 0.9375rem; font-weight: 700; letter-spacing: -0.012em; }

.status-row { display: flex; align-items: center; gap: 10px; margin-bottom: 1rem; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.dot.on { background: var(--ok); box-shadow: 0 0 0 3px var(--ok-soft); }
.dot.off { background: var(--ink-4); }

.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 1rem; margin: 0; }
.stat-grid dt {
  font-family: var(--font-mono);
  font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--ink-3);
}
.stat-grid dd { margin: 5px 0 0; font-size: 1.125rem; font-weight: 600; letter-spacing: -0.01em; }

.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }
.form-grid label { display: flex; flex-direction: column; gap: 6px; font-size: 0.8125rem; font-weight: 500; }
.form-grid small { color: var(--ink-3); font-size: 0.6875rem; line-height: 1.45; }
.form-grid label.checkbox { flex-direction: row; align-items: center; gap: 10px; }
.form-grid label.checkbox input { width: auto; height: auto; accent-color: var(--signal); }

.hint, .muted { color: var(--ink-3); font-size: 0.75rem; margin: 1rem 0 0; }
.err { color: var(--bad); font-size: 0.8125rem; margin: 0.75rem 0 0; }

.events { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.events li { display: flex; align-items: center; gap: 10px; font-size: 0.8125rem; flex-wrap: wrap; }
.events .time { color: var(--ink-4); font-size: 0.6875rem; }
.events a { color: var(--signal); text-decoration: none; }
.events a:hover { text-decoration: underline; }
.tag {
  font-family: var(--font-mono);
  font-size: 0.6875rem; padding: 2px 8px; border-radius: 999px;
  border: 1px solid var(--line); color: var(--ink-3);
}
</style>
