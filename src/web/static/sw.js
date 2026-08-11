const CACHE_NAME = 'jarvis-on-road-v1';
const PRECACHE_URLS = [
  '/static/index.html',
  '/static/css/main.css',
  '/static/js/config.js',
  '/static/js/api.js',
  '/static/js/ws.js',
  '/static/js/dashboard.js',
  '/static/js/leds.js',
  '/static/js/pwa.js',
  '/static/js/app.js',
  '/static/manifest.json',
  '/static/icons/icon.svg',
  '/static/icons/maskable-icon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names.map((name) => {
            if (name !== CACHE_NAME) {
              return caches.delete(name);
            }
          })
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (url.pathname.startsWith('/api/') || url.pathname === '/ws') {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match('/static/index.html').then((cached) => {
          if (cached) return cached;
          return new Response(
            '<h1>Jarvis On Road</h1><p>No hay conexión con la Raspberry y la interfaz no está en caché.</p>',
            { headers: { 'Content-Type': 'text/html' }, status: 503 }
          );
        })
      )
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(request)
        .then((response) => {
          if (
            request.method === 'GET' &&
            response &&
            response.status === 200 &&
            response.type === 'basic'
          ) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => {
          return new Response('', { status: 503, statusText: 'Service Unavailable' });
        });
    })
  );
});
