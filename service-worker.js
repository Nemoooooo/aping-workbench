// 工作台 Service Worker v15
// 策略：
// - 安装时预缓存核心资源（带 no-cache，确保首次安装/更新时拿到最新文件）
// - 从 index.html 提取「内嵌保险数据」写入数据缓存，离线兜底
// - 数据请求：网络优先 + no-cache，失败回退缓存，再失败给 {}
// - 页面导航：网络优先 + no-cache，失败回退缓存
// - 静态资源：缓存优先
// - 激活时清理旧缓存并立即接管页面（clients.claim）
// - 任何情况都返回合法 Response，绝不返回 null
const CACHE = 'workbench-v15';
const CORE = [
  './', './index.html', './tailwind.min.js', './fa.css', './manifest.webmanifest',
  './icon-192.png', './apple-touch-icon.png', './logo-circle.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    // 显式用 no-cache 拉取核心资源，避免浏览器 HTTP 缓存导致安装的是旧版
    await Promise.allSettled(CORE.map(async (u) => {
      try {
        const resp = await fetch(u, { cache: 'no-cache' });
        if (resp && resp.ok) await cache.put(new Request(u), resp);
      } catch (e) { console.warn('[SW] pre-cache failed', u, e); }
    }));
    // 从 index.html 提取内嵌保险数据，写入数据缓存（核心兜底，独立于 HTML 缓存新旧）
    try {
      const htmlRes = await cache.match('./index.html') ||
                       await fetch('./index.html', { cache: 'no-cache' });
      const text = await htmlRes.text();
      const m = text.match(/<script id="embedded-data">([\s\S]*?)<\/script>/);
      if (m) {
        let js = m[1];
        const i = js.indexOf('window.__EMBEDDED__ = ');
        let jsonStr = js.slice(i + 'window.__EMBEDDED__ = '.length).replace(/;\s*$/, '').trim();
        const data = JSON.parse(jsonStr); // <\/ 在 JSON 中会自动解析为 </
        if (data.news) {
          await cache.put(new Request(self.location.origin + '/data/news-analysis.json'),
            new Response(JSON.stringify(data.news), { status: 200, headers: { 'Content-Type': 'application/json; charset=utf-8' } }));
        }
        if (data.ai) {
          await cache.put(new Request(self.location.origin + '/data/ai-briefing.json'),
            new Response(JSON.stringify(data.ai), { status: 200, headers: { 'Content-Type': 'application/json; charset=utf-8' } }));
        }
        console.log('[SW] embedded data cached as offline fallback');
      }
    } catch (e) { console.warn('[SW] extract embedded failed', e); }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
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
  if (url.origin !== self.location.origin) return;
  const isData = url.pathname.endsWith('.json');
  const isNav = req.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname === '/' || url.pathname.endsWith('/');

  if (isData) {
    const normReq = new Request(url.origin + url.pathname, { method: 'GET' });
    event.respondWith((async () => {
      try {
        // 数据请求强制绕过浏览器 HTTP 缓存，确保每次都能看到最新内容
        const res = await fetch(new Request(req, { cache: 'no-cache' }));
        if (res && res.ok) putCache(normReq, res);
        return res;
      } catch (e) {
        const cached = await caches.match(normReq);
        if (cached) return cached;
        return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json; charset=utf-8' } });
      }
    })());
    return;
  }

  if (isNav) {
    event.respondWith(
      fetch(new Request(req, { cache: 'no-cache' }))
        .then((res) => { putCache(req, res); return res; })
        .catch(() => caches.match(req).then((r) => r || caches.match('./index.html').then((x) => x || new Response('offline', { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }))))
    );
    return;
  }

  event.respondWith(
    caches.match(req).then((r) =>
      r || fetch(req).then((res) => { putCache(req, res); return res; })
        .catch(() => new Response('', { status: 200, headers: { 'Content-Type': 'text/plain; charset=utf-8' } }))
    )
  );
});
