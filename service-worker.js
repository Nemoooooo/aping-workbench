// 工作台 Service Worker v11
// 策略：核心资源安装时预缓存；页面/数据 网络优先（保证新鲜），静态资源 缓存优先（快速稳定）；
// 任何情况下都返回合法 Response，绝不返回 null。
const CACHE = 'workbench-v11';
const CORE = [
  './',
  './index.html',
  './tailwind.min.js',
  './fa.css',
  './manifest.webmanifest',
  './icon-192.png',
  './apple-touch-icon.png',
  './logo-circle.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(CORE.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function putCache(req, res) {
  try {
    if (res && res.ok && res.type === 'basic') {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
    }
  } catch (e) {}
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  let url;
  try { url = new URL(req.url); } catch (e) { return; }
  // 跨域请求不拦截，直接走网络（避免返回 null 影响第三方资源）
  if (url.origin !== self.location.origin) return;

  const isData = url.pathname.endsWith('.json');
  const isNav = req.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname === '/' || url.pathname.endsWith('/');

  if (isData || isNav) {
    // 网络优先：保证数据与页面最新；失败回退缓存，最终给合法兜底响应
    event.respondWith(
      fetch(req)
        .then((res) => { putCache(req, res); return res; })
        .catch(() =>
          caches.match(req).then((r) => {
            if (r) return r;
            if (isNav) return caches.match('./index.html').then((x) => x || new Response('offline', { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }));
            return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json; charset=utf-8' } });
          })
        )
    );
    return;
  }

  // 静态资源（CSS/JS/图片）：缓存优先（已预缓存，秒开且离线可用），失败回退网络
  event.respondWith(
    caches.match(req).then((r) =>
      r || fetch(req)
        .then((res) => { putCache(req, res); return res; })
        .catch(() => new Response('', { status: 200, headers: { 'Content-Type': 'text/plain; charset=utf-8' } }))
    )
  );
});
