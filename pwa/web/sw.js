// Service worker de Kreix: guarda la app entera en el movil para que abra sin conexion.
// tools/build_pwa.py rellena la version (cambia con cualquier archivo) y la lista de archivos.
const VERSION = "__VERSION__";
const SHELL = `kreix-${VERSION}`;
// Pyodide y sus paquetes (unos 17 MB, en pyodide/) van en una cache aparte que se conserva entre versiones de la app
// mientras no cambie la de Pyodide: una actualizacion de Kreix no vuelve a descargarlos.
const RUNTIME = "pyodide-__PYODIDE__";
const PYODIDE_FILES = ["__PYODIDE_FILES__"];
const FILES = ["__FILES__"];

self.addEventListener("install", (event) => {
  // la version nueva entra en cuanto se descarga; la app abierta sigue con lo que ya tiene cargado y la proxima vez abre la nueva
  event.waitUntil(Promise.all([
    caches.open(SHELL).then((cache) => cache.addAll(FILES)),
    caches.open(RUNTIME).then(async (cache) => {
      const missing = [];
      for (const file of PYODIDE_FILES) if (!(await cache.match(file))) missing.push(file);
      await cache.addAll(missing);
    }),
  ]).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  // las versiones anteriores de la app (y de Pyodide) se borran
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((k) => k !== SHELL && k !== RUNTIME).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = event.request.url;
  if (event.request.method !== "GET") return;
  if (new URL(url).origin === self.location.origin && new URL(url).pathname.includes("/pyodide/")) {
    event.respondWith(caches.open(RUNTIME).then(async (cache) => {
      const hit = await cache.match(event.request);
      if (hit) return hit;
      const response = await fetch(event.request);
      if (response.ok) cache.put(event.request, response.clone());
      return response;
    }));
    return;
  }
  if (new URL(url).origin !== self.location.origin) return;
  event.respondWith(caches.match(event.request, { ignoreSearch: true }).then((hit) => hit || fetch(event.request)));
});
