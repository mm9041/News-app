/* 简单的 Service Worker：静态资源 cache-first，页面 network-first。
   缓存版本号变了旧缓存会自动清掉。 */

const CACHE_VERSION = 'v1'
const CACHE_NAME = `news-${CACHE_VERSION}`

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME))
  self.skipWaiting()
})

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url)

  // 只处理同源请求，API 请求不缓存（实时数据）
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) {
    return
  }

  // 带 hash 的静态资源：cache-first
  if (/\/assets\//.test(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then(
        cached =>
          cached ||
          fetch(event.request).then(response => {
            const copy = response.clone()
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy))
            return response
          })
      )
    )
    return
  }

  // 页面与其它资源：network-first，失败回缓存（离线可看已访问过的页面）
  event.respondWith(
    fetch(event.request)
      .then(response => {
        const copy = response.clone()
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy))
        return response
      })
      .catch(() => caches.match(event.request).then(cached => cached || caches.match('/')))
  )
})
