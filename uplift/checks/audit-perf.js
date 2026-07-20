const { chromium } = require('/tmp/npm-global/lib/node_modules/playwright');
(async()=>{
 const b=await chromium.launch({args:['--ignore-certificate-errors']});
 const c=await b.newContext({viewport:{width:390,height:844},locale:'ar-KW',ignoreHTTPSErrors:true});
 const p=await c.newPage();
 const errs=[],reqs=[];
 p.on('console',m=>{if(m.type()==='error')errs.push(m.text().slice(0,120))});
 p.on('pageerror',e=>errs.push('PAGEERROR: '+String(e).slice(0,120)));
 p.on('response',async r=>{try{const h=r.headers();reqs.push({u:r.url().slice(0,80),s:r.status(),ct:(h['content-type']||'').split(';')[0],len:+(h['content-length']||0)})}catch{}});
 const t0=Date.now();
 await p.goto('https://isnad.news',{waitUntil:'load',timeout:60000});
 const tLoad=Date.now()-t0;
 await p.waitForTimeout(6000);
 const m=await p.evaluate(()=>{
  const nav=performance.getEntriesByType('navigation')[0]||{};
  const lcp=performance.getEntriesByType('largest-contentful-paint').pop();
  const imgs=[...document.images];
  return {
   dom:document.querySelectorAll('*').length,
   html:document.documentElement.outerHTML.length,
   lang:document.documentElement.lang, dir:document.documentElement.dir,
   title:document.title, titleLen:document.title.length,
   desc:(document.querySelector('meta[name=description]')||{}).content||null,
   og:[...document.querySelectorAll('meta[property^="og:"],meta[name^="twitter:"]')].map(e=>e.getAttribute('property')||e.getAttribute('name')),
   canonical:(document.querySelector('link[rel=canonical]')||{}).href||null,
   ldjson:document.querySelectorAll('script[type="application/ld+json"]').length,
   h1:document.querySelectorAll('h1').length, h2:document.querySelectorAll('h2').length,
   imgsNoAlt:imgs.filter(i=>!i.alt).length, imgsTotal:imgs.length,
   imgsNoLazy:imgs.filter(i=>i.loading!=='lazy').length,
   btnsNoLabel:[...document.querySelectorAll('button,[role=button]')].filter(e=>!e.innerText.trim()&&!e.getAttribute('aria-label')).length,
   inlineStyleTags:document.querySelectorAll('style').length,
   scripts:document.querySelectorAll('script').length,
   ttfb:Math.round(nav.responseStart||0), domInt:Math.round(nav.domInteractive||0),
   loadEv:Math.round(nav.loadEventEnd||0), transfer:nav.transferSize||0,
   lcpMs: lcp?Math.round(lcp.startTime):null,
   items:document.querySelectorAll('#feed .item').length
  };
 });
 const byType={};let total=0;
 reqs.forEach(r=>{byType[r.ct]=(byType[r.ct]||0)+r.len;total+=r.len});
 console.log(JSON.stringify({tLoad,metrics:m,errors:errs.slice(0,8),reqCount:reqs.length,
   bytesByType:Object.fromEntries(Object.entries(byType).sort((a,b)=>b[1]-a[1]).slice(0,8).map(([k,v])=>[k,Math.round(v/1024)+'KB'])),
   totalKB:Math.round(total/1024), fails:reqs.filter(r=>r.s>=400).slice(0,6)},null,1));
 await b.close();
})();
