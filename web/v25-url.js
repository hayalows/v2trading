(()=>{
  const allowed=new Set(['EURUSD','GBPUSD','XAUUSD']);
  const wanted=String(new URLSearchParams(location.search).get('market')||'').toUpperCase();
  let applied=false;
  function copy(){document.title='V2.5 Intelligence Lab · EURUSD · GBPUSD · Gold';const e=document.querySelector('.intro .eyebrow'),p=document.querySelector('.intro p'),b=document.querySelector('.brand span');if(e)e.textContent='V2.5 · Three-market intelligence';if(p)p.textContent='Read EURUSD, GBPUSD and Gold through one market-state workflow. Start with what matters now, then open the chart, research or Ask V2 only when you need more detail.';if(b)b.textContent='Three markets, one research view';document.querySelectorAll('.v25SimHead span').forEach(x=>x.textContent='$500 · 1% risk · M5-refined');const rp=document.querySelector('#v25Research > p');if(rp)rp.textContent='Same M15 V2 detector and frozen midpoint/SL/2.5R geometry, but M5 sequencing is used to resolve more entry/stop/target ordering. Costs remain excluded.'}
  function legacyRefresh(){setTimeout(()=>{try{const fn=globalThis.render;if(typeof fn==='function')fn()}catch(e){console.warn('V2.5 detail sync',e)}},0)}
  function apply(){
    copy();const tabs=[...document.querySelectorAll('[data-v25]')];if(!tabs.length)return;
    tabs.forEach(b=>{if(!b.dataset.v25Bound){b.dataset.v25Bound='1';b.addEventListener('click',()=>{const s=String(b.getAttribute('data-v25')||'').toUpperCase();if(!allowed.has(s))return;const u=new URL(location.href);u.searchParams.set('market',s);history.replaceState({},'',u);legacyRefresh()})}});
    if(!applied&&allowed.has(wanted)){const b=tabs.find(x=>x.getAttribute('data-v25')===wanted);if(b){applied=true;b.click()}}
  }
  const mo=new MutationObserver(apply);mo.observe(document.body,{childList:true,subtree:true});apply();setTimeout(()=>{apply();mo.disconnect()},15000);
})();
