/* Service worker for the Payments Tracker PWA ({{ version }}).
   - Static assets: cache-first (they are versioned by SW_CACHE_VERSION).
   - Pages: network-first; if offline, show the offline page.
   Financial data is never cached, so figures are always live. */
const CACHE = "payments-tracker-{{ version }}";
const PRECACHE = [{% for url in precache %}"{{ url }}"{% if not forloop.last %}, {% endif %}{% endfor %}];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((cache) => cache.put(req, copy));
        return res;
      }))
    );
    return;
  }

  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match("/offline/")));
  }
});
