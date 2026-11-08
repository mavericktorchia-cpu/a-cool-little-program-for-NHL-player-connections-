// Offline support. web/build.py fills in the version and the list of files to keep.
// Pages: try the network first so new puzzles and rosters show up, fall back to the saved copy.
// Shared files carry ?v=<hash> in their URL, so a saved copy is always the right one.
const VERSION = "__VERSION__";
const CACHE = "nhl-connections-" + VERSION;
const PRECACHE = __PRECACHE__;

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(names => Promise.all(names.filter(n => n !== CACHE).map(n => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  if (url.origin !== location.origin) return;

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then(res => {
          const copy = res.clone();
          caches.open(CACHE).then(cache => cache.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req, { ignoreSearch: true }).then(hit => hit || caches.match("./")))
    );
    return;
  }

  event.respondWith(caches.match(req).then(hit => hit || fetch(req)));
});
