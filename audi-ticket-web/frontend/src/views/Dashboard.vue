<template>
  <div class="min-h-screen">
    <!-- Header -->
    <header class="border-b border-white/10 px-4 py-4">
      <div class="max-w-6xl mx-auto flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="text-2xl">🎫</span>
          <h1 class="text-xl font-bold">Audi Ticket Bot</h1>
        </div>
        
        <nav class="flex items-center gap-4">
          <router-link to="/" class="text-white/70 hover:text-white transition-colors" active-class="text-white font-medium">
            Dashboard
          </router-link>
          <router-link to="/tasks" class="text-white/70 hover:text-white transition-colors" active-class="text-white font-medium">
            Tasks
          </router-link>
          <button @click="logout" class="btn btn-secondary text-sm">
            Logout
          </button>
        </nav>
      </div>
    </header>
    
    <!-- Main Content -->
    <main class="max-w-6xl mx-auto p-4">
      <!-- Quick Actions -->
      <div class="grid grid-cols-2 gap-4 mb-6">
        <div class="card">
          <div class="flex items-center gap-3 mb-2">
            <div class="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
              📊
            </div>
            <div>
              <div class="text-2xl font-bold">{{ runningTasks }}</div>
              <div class="text-sm text-white/60">Aktive Tasks</div>
            </div>
          </div>
        </div>
        
        <div class="card">
          <div class="flex items-center gap-3 mb-2">
            <div class="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
              🛒
            </div>
            <div>
              <div class="text-2xl font-bold">{{ successCount }}</div>
              <div class="text-sm text-white/60">Erfolgreiche Carts</div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- New Task Form -->
      <div class="card mb-6">
        <h2 class="text-lg font-semibold mb-4">🚀 Neuen Task starten</h2>
        
        <form @submit.prevent="createAndStartTask" class="space-y-4">
          <div>
            <label class="block text-sm text-white/70 mb-2">Produkt URL</label>
            <input
              v-model="newTask.url"
              type="url"
              placeholder="https://audidefuehrungen2.regiondo.de/..."
              class="input"
              required
            />
          </div>
          
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm text-white/70 mb-2">Menge (1-4)</label>
              <input
                v-model.number="newTask.quantity"
                type="number"
                min="1"
                max="4"
                class="input"
              />
            </div>
            <div>
              <label class="block text-sm text-white/70 mb-2">Threads</label>
              <input
                v-model.number="newTask.threads"
                type="number"
                min="1"
                max="10"
                class="input"
              />
            </div>
          </div>
          
          <button
            type="submit"
            class="btn btn-primary w-full py-3"
            :disabled="taskStore.loading || !newTask.url"
          >
            <span v-if="taskStore.loading">Wird erstellt...</span>
            <span v-else>Task erstellen & starten</span>
          </button>
        </form>
      </div>
      
      <!-- Active Tasks -->
      <div class="card">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold">📋 Aktive Tasks</h2>
          <button @click="taskStore.fetchTasks" class="btn btn-secondary text-sm">
            Aktualisieren
          </button>
        </div>
        
        <div v-if="taskStore.loading && !taskStore.tasks.length" class="text-center py-8 text-white/60">
          Laden...
        </div>
        
        <div v-else-if="!taskStore.tasks.length" class="text-center py-8 text-white/60">
          Keine Tasks vorhanden. Erstelle einen neuen Task oben.
        </div>
        
        <div v-else class="space-y-3">
          <TaskCard
            v-for="task in taskStore.tasks"
            :key="task.id"
            :task="task"
            @start="taskStore.startTask"
            @stop="taskStore.stopTask"
            @delete="taskStore.deleteTask"
          />
        </div>
      </div>
      
      <!-- Logs -->
      <div class="card mt-6">
        <h2 class="text-lg font-semibold mb-4">📝 Live Logs</h2>
        <div class="bg-black/30 rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm">
          <div v-if="!logs.length" class="text-white/40">
            Warte auf Logs...
          </div>
          <div
            v-for="(log, i) in logs"
            :key="i"
            class="py-1"
            :class="{
              'text-green-400': log.level === 'success',
              'text-yellow-400': log.level === 'warning',
              'text-red-400': log.level === 'error',
              'text-white/70': log.level === 'info'
            }"
          >
            [{{ log.timestamp }}] {{ log.message }}
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTaskStore } from '../stores/tasks'
import TaskCard from '../components/TaskCard.vue'

const router = useRouter()
const authStore = useAuthStore()
const taskStore = useTaskStore()

const newTask = ref({
  url: '',
  quantity: 2,
  threads: 1
})

const logs = ref([])
let ws = null

const runningTasks = computed(() => 
  taskStore.tasks.filter(t => t.status === 'running').length
)

const successCount = computed(() => 
  taskStore.tasks.filter(t => t.status === 'success').length
)

async function createAndStartTask() {
  const task = await taskStore.createTask({
    product_url: newTask.value.url,
    quantity: newTask.value.quantity,
    num_threads: newTask.value.threads
  })
  
  if (task) {
    await taskStore.startTask(task.id)
    newTask.value.url = ''
  }
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws?token=${authStore.token}`
  
  ws = new WebSocket(wsUrl)
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    
    if (data.type === 'log') {
      logs.value.push({
        timestamp: new Date().toLocaleTimeString(),
        level: data.data.level,
        message: data.data.message
      })
      // Keep only last 100 logs
      if (logs.value.length > 100) {
        logs.value.shift()
      }
    } else if (data.type === 'task_update') {
      taskStore.updateTask(data.data.task_id, data.data)
      // Fetch full task data if status changed to success (to get cart_token)
      if (data.data.status === 'success') {
        taskStore.fetchTasks()
      }
    } else if (data.type === 'cart_success') {
      // Show notification
      logs.value.push({
        timestamp: new Date().toLocaleTimeString(),
        level: 'success',
        message: `🎉 Warenkorb erfolgreich! Token: ${data.data.token.slice(0, 8)}...`
      })
      taskStore.fetchTasks()
    } else if (data.type === 'ping') {
      // Ignore keepalive
    }
  }
  
  ws.onclose = () => {
    // Reconnect after 3 seconds
    setTimeout(connectWebSocket, 3000)
  }
}

function logout() {
  authStore.logout()
  router.push('/login')
}

onMounted(() => {
  taskStore.fetchTasks()
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
})
</script>
