// ==================== SchoolHub Service Worker ====================
// Purpose: offline caching for static files only.
// API calls are bypassed (they go straight to network).

const CACHE_NAME = "schoolhub-cache-v2";

// Static files to pre-cache (edit as needed)
const PRECACHE_URLS = [
    "/professional_dashboard.html",
    "/index.html",
    "/login.html",
    "/manifest.json"
];

// Files/patterns that should NEVER be intercepted by SW
const BYPASS_PATTERNS = [
    /^\/api\//,
    /\/(announcements|students|fees|attendance|grades|staff|dashboard|settings|ai|exams|parent|teacher|imports|backup|uploads|test-records|filters|schools|superadmin)\b/
];

// ==================== INSTALL ====================
self.addEventListener("install", (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            // Silently fail on missing files (don't break install)
            return Promise.all(
                PRECACHE_URLS.map((url) =>
                    cache.add(url).catch(() => null)
                )
            );
        })
    );
});

// ==================== ACTIVATE ====================
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

// ==================== FETCH ====================
self.addEventListener("fetch", (event) => {
    const req = event.request;
    const url = new URL(req.url);

    // ─────────────────────────────────────────────────────
    // 1. Non-GET requests (POST/PUT/DELETE) → bypass
    // ─────────────────────────────────────────────────────
    if (req.method !== "GET") {
        return;
    }

    // ─────────────────────────────────────────────────────
    // 2. Cross-origin requests → bypass
    // ─────────────────────────────────────────────────────
    if (url.origin !== self.location.origin) {
        return;
    }

    // ─────────────────────────────────────────────────────
    // 3. API endpoints → bypass (always network)
    // ─────────────────────────────────────────────────────
    for (const pattern of BYPASS_PATTERNS) {
        if (pattern.test(url.pathname)) {
            return;
        }
    }

    // ─────────────────────────────────────────────────────
    // 4. HTML navigation → network-first (so users get fresh HTML)
    // ─────────────────────────────────────────────────────
    if (req.mode === "navigate" || req.headers.get("accept")?.includes("text/html")) {
        event.respondWith(
            fetch(req)
                .then((resp) => {
                    const copy = resp.clone();
                    caches.open(CACHE_NAME).then((c) => c.put(req, copy)).catch(() => {});
                    return resp;
                })
                .catch(() => caches.match(req).then((c) => c || caches.match("/professional_dashboard.html")))
        );
        return;
    }

    // ─────────────────────────────────────────────────────
    // 5. Static assets (CSS/JS/images) → cache-first
    // ─────────────────────────────────────────────────────
    event.respondWith(
        caches.match(req).then((cached) => {
            if (cached) return cached;
            return fetch(req)
                .then((resp) => {
                    // Only cache successful, same-origin responses
                    if (resp && resp.status === 200 && resp.type === "basic") {
                        const copy = resp.clone();
                        caches.open(CACHE_NAME).then((c) => c.put(req, copy)).catch(() => {});
                    }
                    return resp;
                })
                .catch(() => {
                    // Offline fallback for images
                    if (req.destination === "image") {
                        return new Response("", { status: 204 });
                    }
                    return new Response("Offline", { status: 503, statusText: "Offline" });
                });
        })
    );
});

// ==================== MESSAGE ====================
self.addEventListener("message", (event) => {
    if (event.data === "SKIP_WAITING") {
        self.skipWaiting();
    }
});