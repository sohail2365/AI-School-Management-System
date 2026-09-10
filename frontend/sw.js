// Minimal service worker — exists only so Chrome/Edge recognize SchoolHub
// as installable. It does NOT cache anything: this app is fully online
// (live data, live login), so offline caching would show stale/broken
// pages instead of a real offline mode. Every request just passes through
// to the network unchanged.
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Pass-through only — no caching, no offline fallback.
  event.respondWith(fetch(event.request));
});
