const CACHE="cfo-cockpit-shell-v6";

const ASSETS=[
  "./",
  "./index.html",
  "./v4.html",
  "./styles.css",
  "./config.js",
  "./app.js",
  "./manifest.webmanifest",
  "./favicon.png",
  "./icon-192.png",
  "./icon-512.png",
  "./quotes.json"
];

self.addEventListener("install",event=>{
  event.waitUntil(
    caches.open(CACHE)
      .then(cache=>cache.addAll(ASSETS))
      .then(()=>self.skipWaiting())
  );
});

self.addEventListener("activate",event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(
        keys
          .filter(key=>key!==CACHE)
          .map(key=>caches.delete(key))
      ))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener("fetch",event=>{
  if(event.request.method!=="GET")return;

  const url=new URL(event.request.url);

  // Dati sempre aggiornati: nessuna risposta dalla cache
  if(
    url.pathname.endsWith("/quotes.json") ||
    url.pathname.endsWith("/news.json") ||
    url.pathname.endsWith("/market.json") ||
    url.pathname.endsWith("/summary.json")
  ){
    event.respondWith(
      fetch(event.request,{cache:"no-store"})
        .catch(()=>caches.match(event.request))
    );
    return;
  }

  // File applicativi aggiornati dal server
  if(
    url.pathname.endsWith("/index.html") ||
    url.pathname.endsWith("/app.js") ||
    url.pathname.endsWith("/config.js") ||
    url.pathname.endsWith("/styles.css") ||
    url.pathname.endsWith("/sw.js")
  ){
    event.respondWith(
      fetch(event.request,{cache:"no-store"})
        .then(response=>{
          const copy=response.clone();
          caches.open(CACHE).then(cache=>{
            cache.put(event.request,copy);
          });
          return response;
        })
        .catch(()=>caches.match(event.request))
    );
    return;
  }

  // Risorse statiche
  event.respondWith(
    caches.match(event.request)
      .then(hit=>hit||fetch(event.request)
        .then(response=>{
          const copy=response.clone();
          caches.open(CACHE).then(cache=>{
            cache.put(event.request,copy);
          });
          return response;
        })
        .catch(()=>caches.match("./index.html"))
      )
  );
});
