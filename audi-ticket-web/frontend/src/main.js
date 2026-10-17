import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

// MUST stay in sync with public/sw.js (NAV_CACHE, NAV_KEY, MSG_SW_NAVIGATE).
// The SW can't import from src without classic-worker gymnastics.
const NAV_CACHE = 'audi-ops-nav'
const NAV_KEY = '/__pending_nav__'
const MSG_SW_NAVIGATE = 'sw-navigate'

const navigateTo = (url) => {
  if (typeof url === 'string' && url.startsWith('/')) {
    router.push(url).catch(() => {})
  }
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .catch((err) => console.warn('SW register failed:', err))
  })

  navigator.serviceWorker.addEventListener('message', (event) => {
    const msg = event.data
    if (msg && msg.type === MSG_SW_NAVIGATE) navigateTo(msg.url)
  })

  // iOS PWA cold-start drops the SW's postMessage; recover via Cache Storage.
  if ('caches' in window) {
    caches.open(NAV_CACHE)
      .then(async (cache) => {
        const resp = await cache.match(NAV_KEY)
        if (!resp) return
        const [url] = await Promise.all([resp.text(), cache.delete(NAV_KEY)])
        navigateTo(url)
      })
      .catch(() => {})
  }
}
