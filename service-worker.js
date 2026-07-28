// 工作台 Service Worker v13
// 目标：GitHub Pages 在国内访问不稳定时，模块数据也不空白。
// 策略：核心资源 + 当日数据在“安装时预缓存”；数据走“稳定缓存键(忽略?t=) + 后台更新(SWR)”；
// 页面网络优先、静态资源缓存优先；任何情况下都返回合法 Response，绝不返回 null。
const CACHE = 'workbench-v13';  // 升版以重新预缓存含内嵌保险数据的 index.html
const CORE = [
  './',
  './index.html',
  './tailwind.min.js',
  './fa.css',
  './manifest.webmanifest',
  './icon-192.png',
  './apple-touch-icon.png',
  './logo-circle.png',
  './data/news-analysis.json',
  './data/ai-briefing.json'
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
  if (url.origin !== self.location.origin) return; // 跨域不拦截

  const isData = url.pathname.endsWith('.json');
  const isNav = req.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname === '/' || url.pathname.endsWith('/');

  if (isData) {
    // 数据：用“去掉查询串”的稳定键做缓存；有缓存先回缓存并后台更新，无缓存走网络，网络失败给 {}
    const normReq = new Request(url.origin + url.pathname, { method: 'GET' });
    event.respondWith(
      caches.match(normReq).then((cached) => {
        const net = fetch(req).then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(normReq, copy)).catch(() => {});
          }
          return res;
        }).catch(() => null);
        if (cached) return cached; // 立即返回缓存，net 在后台更新
        return net.then((res) => res || new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json; charset=utf-8' } }));
      })
    );
    return;
  }

  if (isNav) {
    // 页面：网络优先保证最新，失败回退缓存
    event.respondWith(
      fetch(req)
        .then((res) => { putCache(req, res); return res; })
        .catch(() => caches.match(req).then((r) => r || caches.match('./index.html').then((x) => x || new Response('offline', { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }))))
    );
    return;
  }

  // 静态资源：缓存优先（已预缓存，秒开且离线可用），失败回退网络
  event.respondWith(
    caches.match(req).then((r) =>
      r || fetch(req)
        .then((res) => { putCache(req, res); return res; })
        .catch(() => new Response('', { status: 200, headers: { 'Content-Type': 'text/plain; charset=utf-8' } }))
    )
  );
});
