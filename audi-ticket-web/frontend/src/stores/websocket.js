import { ref } from 'vue'
import { useTaskStore } from './tasks'
import { useCartStore } from './cart'
import { useLogStore } from './logs'

const connected = ref(false)
let ws = null
let reconnectTimer = null
let getTokenFn = null
let failCount = 0
let pingInterval = null

function getWsUrl(token) {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws?token=${token}`
}

export function useWebSocket() {
  function connect(token, tokenGetter) {
    if (ws) disconnect()
    if (tokenGetter) getTokenFn = tokenGetter
    failCount = 0

    const url = getWsUrl(token)
    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      failCount = 0
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        handleMessage(msg)
      } catch {
        // ignore non-JSON (e.g. "pong")
      }
    }

    ws.onclose = () => {
      connected.value = false
      ws = null
      failCount++
      // Stop reconnecting after 3 consecutive failures (likely invalid token)
      if (failCount >= 3) return
      reconnectTimer = setTimeout(() => {
        const freshToken = getTokenFn ? getTokenFn() : null
        if (freshToken) connect(freshToken)
      }, 3000)
    }

    ws.onerror = () => {
      // onclose will fire after this
    }

    // Keepalive ping every 25 seconds
    if (pingInterval) clearInterval(pingInterval)
    pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      } else {
        clearInterval(pingInterval)
      }
    }, 25000)
  }

  function disconnect() {
    getTokenFn = null
    if (pingInterval) {
      clearInterval(pingInterval)
      pingInterval = null
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.onclose = null // prevent auto-reconnect
      ws.close()
      ws = null
    }
    connected.value = false
  }

  function handleMessage(msg) {
    const taskStore = useTaskStore()
    const cartStore = useCartStore()
    const logStore = useLogStore()

    switch (msg.type) {
      case 'task_update': {
        const updates = { status: msg.data.status }
        if (msg.data.recart_at) updates.recart_at = msg.data.recart_at
        taskStore.updateTask(msg.data.task_id, updates)
        break
      }

      case 'scan_update':
        taskStore.updateTask(msg.data.task_id, {
          scan_count: msg.data.scan_count,
          tickets_available: msg.data.tickets_available,
          last_scan_at: msg.data.last_scan_at
        })
        break

      case 'cart_success':
        // Refresh carts from server to get full cart data
        cartStore.fetchCarts()
        // Also update the task with cart token
        taskStore.updateTask(msg.data.task_id, {
          status: 'success',
          cart_token: msg.data.token
        })
        break

      case 'log':
        logStore.addLog(msg.data)
        break

      case 'aco_payment_ready':
        // Auto-open payment page in new tab
        if (msg.data.checkout_url) {
          window.open(msg.data.checkout_url, '_blank')
        }
        cartStore.fetchCarts()
        break

      case 'ping':
        // Server keepalive, ignore
        break
    }
  }

  return {
    connected,
    connect,
    disconnect
  }
}
