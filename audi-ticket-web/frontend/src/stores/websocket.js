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
let everOpened = false  // resync only on REconnects; App does the first fetch
const MAX_RECONNECTS = 12
const MAX_BACKOFF_MS = 30000

function getWsUrl(token) {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws?token=${token}`
}

// iOS drops the socket while the app is in the background and the reconnect
// backoff may have given up. Coming back: revive a dead socket (onopen then
// resyncs), or resync over a live one in case pushes were missed.
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState !== 'visible' || !getTokenFn) return
  if (!ws || ws.readyState >= WebSocket.CLOSING) {
    const getter = getTokenFn
    const token = getter()
    if (token) useWebSocket().connect(token, getter)
  } else {
    useTaskStore().fetchTasks()
  }
})

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
      // Pushes sent while we were disconnected are lost; pull current state.
      if (everOpened) { useTaskStore().fetchTasks(); useCartStore().fetchCarts() }
      everOpened = true
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

    ws.onclose = (ev) => {
      connected.value = false
      ws = null
      // 4001 = server auth rejection (api/websocket.py). No point retrying
      // with the same token — the auth store redirects to /login on the next
      // API call anyway.
      if (ev.code === 4001) return
      failCount++
      if (failCount > MAX_RECONNECTS) {
        console.warn(`WS giving up after ${MAX_RECONNECTS} reconnect attempts`)
        return
      }
      const backoff = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** Math.min(failCount, 5))
      reconnectTimer = setTimeout(() => {
        const freshToken = getTokenFn ? getTokenFn() : null
        if (freshToken) connect(freshToken)
      }, backoff)
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
    failCount = 0
    if (pingInterval) {
      clearInterval(pingInterval)
      pingInterval = null
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.onclose = null
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

      case 'cart_update':
        cartStore.applyCartUpdate(msg.data)
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
