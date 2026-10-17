import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from './api'

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i])
  return window.btoa(binary)
}

export const usePushStore = defineStore('push', () => {
  const supported = ref(
    typeof window !== 'undefined' &&
      'serviceWorker' in navigator &&
      'PushManager' in window
  )
  const permission = ref(
    typeof Notification !== 'undefined' ? Notification.permission : 'default'
  )
  const subscribed = ref(false)
  const busy = ref(false)
  const error = ref(null)

  const isIOS = computed(() => {
    const ua = typeof navigator !== 'undefined' ? navigator.userAgent : ''
    return /iPhone|iPad|iPod/i.test(ua)
  })
  const isStandalone = computed(() => {
    if (typeof window === 'undefined') return false
    return (
      window.navigator.standalone === true ||
      window.matchMedia?.('(display-mode: standalone)').matches
    )
  })
  const needsInstallFirst = computed(() => isIOS.value && !isStandalone.value)

  async function refresh() {
    if (!supported.value) return
    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      subscribed.value = !!sub
      permission.value = Notification.permission
    } catch (e) {
      subscribed.value = false
    }
  }

  async function enable() {
    if (!supported.value || busy.value) return false
    busy.value = true
    error.value = null
    try {
      const perm = await Notification.requestPermission()
      permission.value = perm
      if (perm !== 'granted') {
        error.value = perm === 'denied' ? 'Notifications blocked in browser settings.' : 'Permission not granted.'
        return false
      }

      const { key } = await api.get('/api/push/vapid-public-key')
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key),
      })

      const raw = sub.toJSON()
      await api.post('/api/push/subscribe', {
        endpoint: raw.endpoint,
        keys: { p256dh: raw.keys.p256dh, auth: raw.keys.auth },
        user_agent: navigator.userAgent.slice(0, 300),
      })
      subscribed.value = true
      return true
    } catch (e) {
      error.value = e?.message || 'Push setup failed.'
      return false
    } finally {
      busy.value = false
    }
  }

  async function disable() {
    if (!supported.value || busy.value) return
    busy.value = true
    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      if (sub) {
        await api.post('/api/push/unsubscribe', { endpoint: sub.endpoint }).catch(() => {})
        await sub.unsubscribe()
      }
      subscribed.value = false
    } finally {
      busy.value = false
    }
  }

  return {
    supported,
    permission,
    subscribed,
    busy,
    error,
    isIOS,
    isStandalone,
    needsInstallFirst,
    refresh,
    enable,
    disable,
  }
})
