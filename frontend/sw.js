// Minimal service worker — exists only so Chrome/Edge recognize SchoolHub
// as installable. It does NOT cache anything: this app is fully online
// (live data, live login), so offline caching would show stale/broken
// pages instead of a real offline mode. Every request just passes through
// to the network unchanged.
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  // Pass-through only — no caching, no offline fallback.
  // On network failure, return a proper network error (not a fake 503)
  // so the browser handles it natively without console spam.
  event.respondWith(
    fetch(event.request).catch(() => Response.error())
  );
});