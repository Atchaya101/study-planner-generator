// ============================================================
// sw.js — StudyPlan Service Worker
// Handles background push notifications and offline caching
// ============================================================

const CACHE_NAME = "studyplan-v1";

// ── Install: cache key static assets ─────────────────────────
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache =>
      cache.addAll(["/", "/static/css/style.css", "/static/js/main.js"])
    )
  );
  self.skipWaiting();
});

// ── Activate: clean old caches ────────────────────────────────
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch: network-first, fallback to cache ───────────────────
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// ── Push: show notification ───────────────────────────────────
self.addEventListener("push", event => {
  let data = { title: "StudyPlan Reminder", body: "Time to study!", icon: "/static/img/icon-192.png" };
  try { data = { ...data, ...event.data.json() }; } catch(e) {}

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body:    data.body,
      icon:    data.icon || "/static/img/icon-192.png",
      badge:   "/static/img/icon-192.png",
      tag:     "studyplan-reminder",
      renotify: true,
      actions: [{ action: "open", title: "Open App" }]
    })
  );
});

// ── Notification click: open app ──────────────────────────────
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: "window" }).then(clientList => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && "focus" in client)
          return client.focus();
      }
      if (clients.openWindow) return clients.openWindow("/");
    })
  );
});
