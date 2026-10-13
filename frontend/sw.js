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
  const url = new URL(event.request.url);

  // ✅ API calls ko SW se bypass karo — seedha network pe jao
  if (url.origin !== self.location.origin ||
      url.pathname.startsWith("/api/") ||
      /\/(announcements|students|fees|attendance|grades|staff|dashboard|settings|ai)/.test(url.pathname)) {
      return;
  }

  // baaki static files ke liye existing cache-first logic rakho
  event.respondWith(/* ... aapka existing code ... */);
});