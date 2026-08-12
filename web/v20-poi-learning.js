(()=>{
  const ENDPOINT='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/paper-trade-engine?symbol=EURUSD,GBPUSD&bars=0';
  let v20Data=null,busy=false;
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  const pct=v=>Number.isFinite(Number(v))?`${Math.max(0,Number(v))*100<10?(Math.max(0,Number(v))*100).toFixed(1):(Math.max(0,Number(v))*100).toFixed(0)}%`:'—';
  const num=(v,d=3)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
  const cap=s=>String(s||'').replaceAll('_',' ').replace(/\b\w/g,m=>m.toUpperCase());
  const lifecycle={untouched:'Untouched',grazed:'Grazed',partially_mitigated:'Partially mitigated',midpoint_touched:'Midpoint touched',deep_unfilled:'Deep visit, midpoint unresolved',distal_touched:'Distal edge touched',invalidated_close_through:'Closed through distal edge'};
  const reason={superseded_by_newer_same_direction_plan:'Superseded by a newer same-direction formation',distal_close_invalidated:'Closed through the distal edge',outside_studied_tail:'Outside the studied waiting-time tail'};

  function activePlan(symbol){
    const xs=(v20Data?.trades||[]).filter(t=>t.symbol===symbol);
    return xs.find(t=>t.status==='open'&&t.focus_active!==false)||xs.find(t=>t.status==='armed'&&t.focus_active!==false)||null;
  }
  function researchPlan(symbol){
    const xs=(v20Data?.trades||[]).filter(t=>t.symbol===symbol&&t.status==='armed'&&t.focus_active===false);
    return xs[0]||null;
  }
  function currentSymbol(){
    if(typeof selected!=='undefined'&&selected)return selected;
    const active=document.querySelector('.pairSwitch button.active,.pairSwitch .active');
    const text=active?.textContent||'';
    return text.includes('GBP')?'GBPUSD':'EURUSD';
  }
  function chip(text){return `<span class="chip">${esc(text)}</span>`}
  function ensureMounts(){
    if(!document.getElementById('v20LifecycleSlot')){
      const anchor=document.getElementById('paperTradeSlot')||document.getElementById('poiWatchSlot');
      if(anchor){const d=document.createElement('div');d.id='v20LifecycleSlot';anchor.insertAdjacentElement('afterend',d)}
    }
    if(!document.getElementById('poiDepthLearning')){
      const view=document.getElementById('evidenceView');
      if(view){const a=document.createElement('article');a.id='poiDepthLearning';a.className='card v20DepthLearning';const shadow=document.getElementById('shadowArenaResearch');if(shadow)shadow.insertAdjacentElement('afterend',a);else view.querySelector('.stats')?.insertAdjacentElement('afterend',a)}
    }
    const frozen=[...document.querySelectorAll('#tradesView .card')].find(x=>x.textContent?.includes('Frozen geometry'));
    if(frozen&&!frozen.dataset.v20){frozen.dataset.v20='1';const h=frozen.querySelector('h3');if(h)h.textContent='50% baseline → sweep stop → 2.5R';const p=frozen.querySelector('p');if(p)p.textContent='The 50% POI midpoint remains the baseline paper entry. Alternative depths from 0% to 100% are now tracked only in a prospective research shadow and cannot change Focus automatically.'}
  }
  function lifecycleCard(t){
    if(!t)return `<article class="card v20Lifecycle"><div class="cardLabel"><span class="material-symbols-rounded">route</span>POI lifecycle</div><h3>No active baseline plan</h3><p>V2 is still collecting formation and POI evidence. Historical plans remain in the journal but do not compete for Focus when they are superseded.</p></article>`;
    const pen=pct(t.max_poi_penetration),state=lifecycle[t.poi_lifecycle_state]||cap(t.poi_lifecycle_state||'untouched');
    return `<article class="card v20Lifecycle"><div class="cardLabel"><span class="material-symbols-rounded">route</span>POI lifecycle</div><h3>${esc(t.symbol)} ${esc(cap(t.direction))} · ${esc(state)}</h3><p>The 50% midpoint remains the baseline paper entry. POI penetration is now tracked continuously so a graze, partial mitigation, midpoint touch and distal traversal are no longer collapsed into one binary flag.</p><div class="paperMeta">${chip(`Max penetration ${pen}`)}${chip(t.focus_active===false?'Research watch':'Focus active')}${chip('Baseline 50%')}</div></article>`;
  }
  function researchWatchCard(t){
    if(!t)return '';
    const why=reason[t.focus_suppression_reason]||'Retained for research, not the current Focus plan';
    return `<article class="card v20ResearchWatch"><div class="cardLabel"><span class="material-symbols-rounded">visibility</span>Research watch</div><h3>${esc(t.symbol)} ${esc(cap(t.direction))} old plan</h3><p>${esc(why)}. The plan is not deleted: V2 continues recording its eventual midpoint/depth outcomes so the data can test lifecycle assumptions without presenting the old setup as the current opportunity.</p><div class="paperMeta">${chip(lifecycle[t.poi_lifecycle_state]||cap(t.poi_lifecycle_state))}${chip(`Max penetration ${pct(t.max_poi_penetration)}`)}${t.pre_entry_target_reached?chip('Original target already delivered'):''}</div></article>`;
  }
  function depthLearningCard(){
    const d=v20Data?.depthLearning;if(!d)return '<div class="cardLabel"><span class="material-symbols-rounded">experiment</span>POI depth learning</div><h3>Loading depth evidence…</h3>';
    const h=d.historicalM5||{},by=d.byDepth||[],pros=Number(d.prospectiveRows||0),back=Number(d.backfilledRows||0);
    const chosen=[20,40,50,65,85].map(x=>by.find(r=>Number(r.depthPct)===x)).filter(Boolean);
    const rows=chosen.map(r=>`<div class="v20DepthRow"><b>${r.depthPct}%</b><span>${r.frozen} prospective setups</span><span>${r.scored} scored</span><span>${r.performanceVisible&&r.meanR!=null?`${Number(r.meanR)>=0?'+':''}${num(r.meanR,3)}R`:'withheld'}</span></div>`).join('');
    return `<div class="cardLabel"><span class="material-symbols-rounded">experiment</span>POI depth learning</div><h3>50% stays baseline. Alternatives learn in shadow.</h3><p>The M5 historical scan found 40% descriptively stronger in the pooled sample, but the chronological test was worse than midpoint (${num(h.walkforwardDeltaR,3)}R; 95% interval ${num(h.walkforward95?.[0],3)} to ${num(h.walkforward95?.[1],3)}). V2 therefore did not change the baseline paper-entry rule.</p><div class="paperMeta">${chip(`Prospective shadow rows ${pros}`)}${chip(`Backfilled rows ${back}`)}${chip('No automatic promotion')}</div><div class="v20DepthGrid">${rows}</div><div class="paperNotice"><strong>Prospective gate</strong>Backfilled observations never count toward promotion. A depth’s performance remains hidden until at least 30 scored prospective observations, and no depth can alter Focus automatically.</div>`;
  }
  function rewriteVisiblePaperPlan(symbol){
    const active=activePlan(symbol),old=researchPlan(symbol);
    const overview=document.getElementById('paperTradeSlot');
    if(overview&&old&&!active){overview.innerHTML=`<article class="card"><div class="cardLabel"><span class="material-symbols-rounded">smart_toy</span>Automatic paper trade</div><h3>No current baseline plan</h3><p>The older ${esc(symbol)} plan is still being tracked for research, but it has been removed from Focus because ${esc((reason[old.focus_suppression_reason]||'its lifecycle evidence is stale').toLowerCase())}.</p><div class="paperMeta">${chip('50% baseline unchanged')}${chip('Research watch retained')}</div></article>`}
    const current=document.getElementById('paperCurrent');
    if(current&&old&&!active){current.innerHTML=`<div class="cardLabel"><span class="material-symbols-rounded">visibility</span>Research watch</div><h3>${esc(symbol)} old plan is not a current opportunity</h3><p>${esc(reason[old.focus_suppression_reason]||'The plan remains available for research only.')} The historical record and alternative-depth shadows continue updating.</p><div class="paperMeta">${chip(lifecycle[old.poi_lifecycle_state]||cap(old.poi_lifecycle_state))}${chip(`Max penetration ${pct(old.max_poi_penetration)}`)}${chip('50% midpoint not replaced')}</div>`}
  }
  function render(){
    ensureMounts();if(!v20Data)return;const symbol=currentSymbol();
    const host=document.getElementById('v20LifecycleSlot');if(host)host.innerHTML=lifecycleCard(activePlan(symbol))+researchWatchCard(researchPlan(symbol));
    const research=document.getElementById('poiDepthLearning');if(research)research.innerHTML=depthLearningCard();
    rewriteVisiblePaperPlan(symbol);
  }
  async function refresh(){
    if(busy)return;busy=true;
    try{v20Data=await (globalThis.__V2DataBus?.paper?globalThis.__V2DataBus.paper('light'):fetch(ENDPOINT,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('v20 paper endpoint');return r.json()}));render()}
    catch(e){console.warn('v2.0 POI learning unavailable',e)}finally{busy=false}
  }
  document.addEventListener('click',e=>{if(e.target.closest('.pairSwitch,.pairSwitch button'))setTimeout(render,50)});
  document.getElementById('refresh')?.addEventListener('click',()=>setTimeout(refresh,250));
  const primary=window.__V2_PRIMARY_V25===true;
  if(typeof setView==='function'){const baseSetView=setView;setView=function(id){baseSetView(id);if(id==='evidenceView'&&primary)refresh()}}
  ensureMounts();if(!primary){refresh();setInterval(refresh,60_000);setInterval(render,5_000)}else if(document.getElementById('evidenceView')?.classList.contains('active'))refresh();
})();
