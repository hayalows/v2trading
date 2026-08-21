(()=>{
  if(globalThis.__v34MarketMapLoaded)return;globalThis.__v34MarketMapLoaded=true;
  const ENDPOINT='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/trader-brief';
  const $=(s,r=document)=>r.querySelector(s);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pair=()=>{try{return typeof selected!=='undefined'?selected:$('.pairBtn.active')?.dataset.pair||'EURUSD'}catch{return $('.pairBtn.active')?.dataset.pair||'EURUSD'}};
  const cap=v=>String(v??'mixed').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
  const f=v=>Number.isFinite(Number(v))?Number(v).toFixed(2):'—';
  let payload=null,busy=false;
  const current=()=>payload?.pairs?.find(x=>x.symbol===pair())||null;
  function ensure(){
    const research=$('.researchInner'),fallback=$('#focusBoard'),root=research||fallback;if(!root)return null;
    let card=$('#v34MarketMap');
    if(!card){card=document.createElement('article');card.id='v34MarketMap';card.className='v34MapCard';if(research)research.prepend(card);else{const grid=fallback?.querySelector('.focusGrid'),note=fallback?.querySelector('.v15ResearchNote');(note||grid||fallback?.lastElementChild)?.insertAdjacentElement('afterend',card)}}
    else if(research&&card.parentElement!==research)research.prepend(card);
    return card;
  }
  function tf(mi,key,label){const s=mi?.timeframes?.[key]?.structure?.label||'mixed';return `<div class="v34Tf ${esc(s)}"><span>${label}</span><b>${esc(cap(s))}</b></div>`}
  function render(){
    const card=ensure(),p=current(),mi=p?.marketMap;if(!card)return;
    if(!mi){const html='<div class="v34MapHead"><div><span>Market map</span><strong>Building higher-timeframe context</strong></div><small>Research context only</small></div>';if(card.innerHTML!==html)card.innerHTML=html;return}
    const h=mi.higherTimeframeContext||{},near=mi.nearestLiquidity?.[0],poi=mi.poi||{},m15=mi.candles?.m15;
    const dir=h.formationDirection?String(h.formationDirection).toUpperCase():'NO DIRECTION';
    const nearText=near?`${cap(near.kind)} · ${f(near.distanceAtr)} ATR away`:'No mapped major level nearby';
    const impulse=poi.available?`${poi.displacement?.strong?'Strong':'Normal'} BOS displacement · FVG ${poi.fvg?.present?'present':'not present'}`:'Impulse grading starts after BOS confirms';
    const html=`<div class="v34MapHead"><div><span>Market map · ${esc(p.symbol)}</span><strong>${esc(dir)} formation · ${esc(cap(h.label||'mixed'))} higher-timeframe structure</strong></div><small>Research context · no trade veto</small></div><div class="v34TfGrid">${tf(mi,'mn1','MN')}${tf(mi,'w1','W')}${tf(mi,'d1','D')}${tf(mi,'h4','4H')}${tf(mi,'h1','1H')}${tf(mi,'m15','15M')}</div><div class="v34MapSignals"><div><span>Nearest mapped liquidity</span><b>${esc(nearText)}</b></div><div><span>Current M15 candle</span><b>${esc(cap(m15?.pattern||'ordinary'))}</b></div><div><span>POI impulse</span><b>${esc(impulse)}</b></div></div><details class="v34MapWhy"><summary>How V2 is using this</summary><p>Monthly and Weekly structure, repeated highs/lows, session location, displacement, FVG and candle shape are recorded with each live formation. The four-year test did not justify a universal higher-timeframe or candlestick veto, so the frozen midpoint entry, structural stop and 2.5R target remain unchanged.</p></details>`;
    if(card.innerHTML!==html)card.innerHTML=html;
  }
  async function load(){if(busy)return;busy=true;try{const r=await fetch(ENDPOINT,{cache:'no-store'});if(r.ok){payload=await r.json();window.v34MarketMap=payload;render()}}catch(e){console.warn('V3.4 market map',e)}finally{busy=false}}
  document.addEventListener('click',e=>{if(e.target.closest?.('[data-pair]'))setTimeout(render,60)});
  new MutationObserver(()=>requestAnimationFrame(render)).observe(document.documentElement,{subtree:true,childList:true});
  ensure();load();setInterval(()=>{if(!document.hidden)load()},30000);
})();