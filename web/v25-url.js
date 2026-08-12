(()=>{
  const allowed=new Set(['EURUSD','GBPUSD','XAUUSD']);
  const wanted=String(new URLSearchParams(location.search).get('market')||'').toUpperCase();
  let applied=false;
  function apply(){
    const tabs=[...document.querySelectorAll('[data-v25]')];if(!tabs.length)return;
    tabs.forEach(b=>{if(!b.dataset.v25Bound){b.dataset.v25Bound='1';b.addEventListener('click',()=>{const s=String(b.getAttribute('data-v25')||'').toUpperCase();if(!allowed.has(s))return;const u=new URL(location.href);u.searchParams.set('market',s);history.replaceState({},'',u)})}});
    if(!applied&&allowed.has(wanted)){const b=tabs.find(x=>x.getAttribute('data-v25')===wanted);if(b){applied=true;b.click()}}
  }
  const mo=new MutationObserver(apply);mo.observe(document.body,{childList:true,subtree:true});apply();setTimeout(()=>{apply();mo.disconnect()},15000);
})();
