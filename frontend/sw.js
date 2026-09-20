// Minimal service worker — exists only so Chrome/Edge recognize SchoolHub
// as installable. It does NOT cache anything: this app is fully online
// (live data, live login), so offline caching would show stale/broken
// pages instead of a real offline mode. Every request just passes through
// to the network unchanged.
self.addEventListener("install", (event) => {
  // Take over immediately, don't wait for old tabs to close.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Claim all clients so this new SW replaces the old one right away.
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  // Pass-through only — no caching, no offline fallback.
  // Wrapped in catch so a blocked/failed request (e.g. a 404 or during
  // a Vercel auth-gated preview) resolves to a clean 503 response instead
  // of an unhandled promise rejection that spams the console.
  event.respondWith(
    fetch(event.request).catch(() => {
      return new Response("Network error — please check your connection.", {
        status: 503,
        statusText: "Service Unavailable",
        headers: { "Content-Type": "text/plain" },
      });
    })
  );
});