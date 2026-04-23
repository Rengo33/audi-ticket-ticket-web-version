/* Audi Ticket Ops service worker — push notifications only, no offline cache. */

// Bump when this file changes; forces waiting installs to activate.
const CACHE_VERSION = 'v1';

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
  event.waitUntil((async () => {
    const clientList = await self.clients.matchAll({
      type: 'window',
      includeUncontrolled: true,
    });
    for (const client of clientList) {
      try {
        const u = new URL(client.url);
        if (u.pathname === target || u.pathname.startsWith(target)) {
          await client.focus();
          return;
        }
      } catch (_) { /* ignore */ }
    }
    await self.clients.openWindow(target);
  })());
});
