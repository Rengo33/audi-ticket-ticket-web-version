<template>
  <div class="card">
    <div class="flex items-start justify-between">
      <div class="flex-1">
        <div class="flex items-center gap-2 mb-2">
          <span class="badge" :class="statusClass">
            {{ statusText }}
          </span>
          <span v-if="task.status === 'running'" class="text-sm text-gray-400">
            Scan #{{ task.scan_count }}
          </span>
          <span v-if="task.status === 'running'" class="text-sm" :class="task.tickets_available > 0 ? 'text-green-600' : 'text-orange-600'">
            • {{ task.tickets_available > 0 ? `${task.tickets_available} verfügbar` : 'Keine Tickets' }}
          </span>
        </div>
        
        <div class="text-sm text-gray-500 truncate mb-1" :title="task.product_url">
          {{ task.product_url }}
        </div>
        
        <div class="text-sm text-gray-400">
          Menge: {{ task.quantity }} • Threads: {{ task.num_threads }}
          <span v-if="task.event_id"> • Event: {{ task.event_id }}</span>
        </div>
        
        <div v-if="detailed && task.error_message" class="mt-2 p-2 bg-red-500/20 rounded text-sm text-red-400">
          {{ task.error_message }}
        </div>
        
        <!-- Checkout Link for successful carts -->
        <div v-if="task.status === 'success' && task.cart_token" class="mt-3 pt-3 border-t border-gray-200">
          <a
            :href="`/checkout/${task.cart_token}/cart`"
            target="_blank"
            class="btn btn-primary inline-flex items-center gap-2"
          >
            📱 Zur Kasse
          </a>
          <button
            @click="copyCheckoutLink"
            class="btn btn-secondary ml-2 text-sm"
          >
            Link kopieren
          </button>
        </div>
      </div>
      
      <div class="flex items-center gap-2 ml-4">
        <button
          v-if="task.status === 'pending' || task.status === 'stopped' || task.status === 'failed'"
          @click="$emit('start', task.id)"
          class="btn btn-primary"
        >
          ▶️ Start
        </button>
        
        <button
          v-if="task.status === 'running' || task.status === 'success' || task.status === 'waiting'"
          @click="$emit('stop', task.id)"
          class="btn btn-danger"
        >
          ⏹️ Stop
        </button>
        
        <button
          v-if="task.status !== 'running' && task.status !== 'success' && task.status !== 'waiting'"
          @click="confirmDelete"
          class="btn btn-secondary"
        >
          🗑️
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  task: {
    type: Object,
    required: true
  },
  detailed: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['start', 'stop', 'delete'])

const statusClass = computed(() => {
  const classes = {
    'running': 'badge-running',
    'success': 'badge-success',
    'waiting': 'badge-waiting',
    'failed': 'badge-failed',
    'pending': 'badge-pending',
    'stopped': 'badge-stopped'
  }
  return classes[props.task.status] || 'badge-pending'
})

const statusText = computed(() => {
  const texts = {
    'running': '🔄 Läuft',
    'success': '✅ Erfolgreich',
    'waiting': '⏳ Re-Cart Countdown',
    'failed': '❌ Fehler',
    'pending': '⏳ Wartend',
    'stopped': '⏸️ Gestoppt'
  }
  return texts[props.task.status] || props.task.status
})

function confirmDelete() {
  if (confirm('Task wirklich löschen?')) {
    emit('delete', props.task.id)
  }
}

function copyCheckoutLink() {
  const url = `${window.location.origin}/checkout/${props.task.cart_token}/cart`
  navigator.clipboard.writeText(url)
  alert('Link kopiert!')
}
</script>
