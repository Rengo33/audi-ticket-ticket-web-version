/* Audi Ticket Ops service worker — push notifications only, no offline cache. */

// Bump when this file changes; forces waiting installs to activate.
const CACHE_VERSION = 'v3';

// MUST stay in sync with src/main.js — the SW can't import ES modules from src.
const NAV_CACHE = 'audi-ops-nav';
const NAV_KEY = '/__pending_nav__';
const MSG_SW_NAVIGATE = 'sw-navigate';

async function stashPendingNav(url) {
  try {
    const cache = await caches.open(NAV_CACHE);
    await cache.put(NAV_KEY, new Response(url, { headers: { 'content-type': 'text/plain' } }));
  } catch (_) { /* ignore */ }
}

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (_) {
    payload = { title: 'Audi Ticket Ops', body: event.data ? event.data.text() : '' };
  }
  const {
    title = 'Audi Ticket Ops',
    body = '',
    url = '/',
    tag,
  } = payload;
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag,
      icon: '/icons/icon-192.png',
      badge: '/icons/badge-72.png',
      data: { url, version: CACHE_VERSION },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';
  const absoluteTarget = new URL(target, self.location.origin).href;
  event.waitUntil((async () => {
    // Stash first: iOS PWA often relaunches at start_url and drops postMessage.
    await stashPendingNav(target);

    const clientList = await self.clients.matchAll({
      type: 'window',
      includeUncontrolled: true,
    });
    for (const client of clientList) {
      let sameOrigin = false;
      try { sameOrigin = new URL(client.url).origin === self.location.origin; } catch (_) { /* ignore */ }
      if (!sameOrigin) continue;
      try {
        client.postMessage({ type: MSG_SW_NAVIGATE, url: target });
        await client.focus();
      } catch (_) { /* ignore */ }
      return;
    }
    try { await self.clients.openWindow(absoluteTarget); } catch (_) { /* ignore */ }
  })());
});
