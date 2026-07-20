const { chromium } = require('/tmp/npm-global/lib/node_modules/playwright');
(async()=>{
 const b=await chromium.launch({args:['--ignore-certificate-errors']});
 const c=await b.newContext({viewport:{width:390,height:844},locale:'ar-KW',ignoreHTTPSErrors:true});
 const p=await c.newPage();
 const fonts=[],audio=[];
 p.on('response',r=>{const u=r.url();const ct=(r.headers()['content-type']||'');
   if(/font|woff/.test(ct)||/\.woff2?$/.test(u))fonts.push({u:u.split('/').pop().slice(0,45),kb:Math.round((+r.headers()['content-length']||0)/1024)});
   if(/audio/.test(ct))audio.push({u:u.split('/').pop().slice(0,45),kb:Math.round((+r.headers()['content-length']||0)/1024)});});
 await p.goto('https://isnad.news',{waitUntil:'load',timeout:60000});
 await p.waitForTimeout(5000);
 const x=await p.evaluate(()=>({
   audioEls:[...document.querySelectorAll('audio')].map(a=>({preload:a.preload,src:(a.currentSrc||a.src||'').split('/').pop()})),
   headings:[...document.querySelectorAll('h1,h2,h3,h4')].map(h=>h.tagName+':'+h.innerText.trim().slice(0,28)).slice(0,14),
   hasSW:'serviceWorker' in navigator && !!navigator.serviceWorker.controller,
   manifest:!!document.querySelector('link[rel=manifest]'),
   rss:!!document.querySelector('link[type="application/rss+xml"]'),
   skipLink:!!document.querySelector('a[href^="#"][class*=skip],a[href="#main"]'),
   landmarks:{main:document.querySelectorAll('main').length,nav:document.querySelectorAll('nav').length,
              header:document.querySelectorAll('header').length,footer:document.querySelectorAll('footer').length},
   ariaLive:document.querySelectorAll('[aria-live]').length,
   canvas:document.querySelectorAll('canvas').length,
   feedItems:document.querySelectorAll('#feed .item').length,
   inlineCSSkb:Math.round([...document.querySelectorAll('style')].reduce((s,e)=>s+e.textContent.length,0)/1024),
   inlineJSkb:Math.round([...document.querySelectorAll('script:not([src])')].reduce((s,e)=>s+e.textContent.length,0)/1024)
 }));
 console.log(JSON.stringify({fonts,audio,...x},null,1));
 await b.close();
})();
