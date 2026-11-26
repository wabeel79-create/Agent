/* Service worker : met en cache l'interface ; les données passent toujours par le serveur du cabinet. */
const CACHE = "kapsi-q-v13";
const SHELL = ["/", "/static/styles.css", "/static/app.js", "/static/campus.js", "/manifest.webmanifest", "/static/icons/icon.svg", "/static/chart.umd.js", "/static/qrcode.js"];

self.addEventListener("install", (e) => e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return; // API : réseau uniquement
  e.respondWith(fetch(e.request).then((r) => {
    const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return r;
  }).catch(() => caches.match(e.request)));
});
