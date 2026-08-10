(()=>{
  const PAPER_FOCUS='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/paper-trade-engine?symbol=EURUSD,GBPUSD';
  const REVISIT={
    EURUSD:[{b:8,h:2,r:.2968},{b:24,h:6,r:.5065},{b:48,h:12,r:.6337},{b:96,h:24,r:.7241},{b:192,h:48,r:.8137}],
    GBPUSD:[{b:8,h:2,r:.3409},{b:24,h:6,r:.5909},{b:48,h:12,r:.6878},{b:96,h:24,r:.7713},{b:192,h:48,r:.8429}]
  };
  let fp={trades:[]},loading=false;
  const safe=(v)=>typeof esc==='function'?esc(v):String(v??'');
  const price=(v)=>Number.isFinite(Number(v))?Number(v).toFixed(5):'—';
  const tradesFor=(symbol)=>(fp.trades||[]).filter(t=>t.symbol===symbol);
  const currentTrade=(symbol=selected)=>{const xs=tradesFor(symbol);return xs.find(t=>t.status==='open')||xs.find(t=>t.status==='armed')||xs[0]||null};
  function annotatePairBadges(){
    document.querySelectorAll('[data-pair]').forEach(btn=>{
      const t=currentTrade(btn.dataset.pair),small=btn.querySelector('.pairMeta small');if(!small||!t)return;
      if(t.status==='open')small.textContent='Paper trade open · SL/TP tracking';
      else if(t.status==='armed')small.textContent=`Paper plan waiting for POI · ${t.pending_age_bars??0} bars`;
    });
  }
  function ensureResearchModelCard(){
    const view=document.getElementById('evidenceView');if(!view||document.getElementById('v15RevisitModel'))return;
    const gate=view.querySelector('#inferenceGate')?.closest('.card');
    const card=document.createElement('article');card.className='card';card.id='v15RevisitModel';card.style.marginTop='12px';
    card.innerHTML='<div class="cardLabel"><span class="material-symbols-rounded">model_training</span>Conditional POI revisit research</div><h3>Static Stage-6 model passed the 12-hour research gate.</h3><p>Walk-forward 2022–2025 testing used 1,262 out-of-sample candidates. At the preregistered 48-bar horizon, AUC was <strong>0.627</strong> and Brier score improved from <strong>0.2268</strong> for the base-rate benchmark to <strong>0.2175</strong>. Calibration improved in 3 of 4 test years.</p><div class="v15ResearchNote"><strong>Why it is not on Focus:</strong> discrimination is useful but modest, and the 96-bar model failed to improve Brier score. This remains an accepted research candidate, not a current-trade probability, win probability, or signal.</div>';
    if(gate)gate.insertAdjacentElement('afterend',card);else view.querySelector('.stats')?.insertAdjacentElement('afterend',card);
  }
  function statusFor(s,t){
    const stage=Number(s?.formation_stage||0);
    if(t?.status==='open')return {label:'PAPER TRADE OPEN',tone:'good',summary:'The midpoint was reached. The research engine is now tracking the frozen stop and 2.5R target.'};
    if(t?.status==='armed')return {label:'WAIT FOR POI',tone:'warn',summary:'A valid paper plan is armed. No entry is counted until price reaches the POI midpoint.'};
    if(stage>=6)return {label:'POI READY',tone:'warn',summary:'BOS and a fresh POI are confirmed. Inspect the location and wait for the entry rule.'};
    if(stage===5)return {label:'BOS CONFIRMED',tone:'warn',summary:'Structure has broken. The next job is to identify and validate the fresh POI.'};
    if(stage>=3)return {label:'WATCH STRUCTURE',tone:'',summary:stage===4?'A sweep exists. Wait for BOS before treating a POI as valid.':'A meaningful liquidity event exists. Do not anticipate the next structural step.'};
    return {label:'NO FOCUS',tone:'',summary:'There is no mature V2 formation requiring attention right now.'};
  }
  function currentContextLabel(i){const x=i?.brief?.context;return x==='supportive'?'Higher timeframes support it':x==='conflicting'?'Higher timeframes conflict':x==='mixed'?'Higher timeframes are mixed':'No directional context yet'}
  function planContext(t){
    if(!t||!['armed','open'].includes(t.status))return null;
    const d=t.context?.diagnostics||{},x=d.structureContext,tr=t.context?.trends||{},labels=['d1','h4','h1','m15'].map(k=>tr[k]?`${k.toUpperCase()} ${tr[k]}`:null).filter(Boolean);
    const title=x==='supportive'?'Plan formed with supportive HTF':x==='conflicting'?'Plan formed against HTF context':'Plan context at Stage 6';
    const detail=`At plan creation: ${labels.length?labels.join(' · '):'HTF detail unavailable'}. Current detector is Stage ${state()?.formation_stage??'—'}/8 (${String(state()?.formation_code||'unknown').replaceAll('_',' ').toLowerCase()}) in ${state()?.regime||'unknown'} regime.`;
    return {title,detail};
  }
  function nextTrigger(s,t){
    const stage=Number(s?.formation_stage||0);
    if(t?.status==='open')return `Track SL ${price(t.stop_price)} and TP ${price(t.target_price)}. No new paper entry is needed.`;
    if(t?.status==='armed')return `Wait for price to reach midpoint ${price(t.entry_price)}. The POI is ${price(t.poi_low)}–${price(t.poi_high)}.`;
    if(stage>=6&&s?.poi_low!=null)return `Watch for price to return into ${price(s.poi_low)}–${price(s.poi_high)}. The midpoint becomes the research entry.`;
    if(stage===5)return 'Wait for a fresh POI to be identified. Do not invent an entry zone.';
    if(stage===4)return 'Wait for BOS. A POI is not valid yet.';
    if(stage===3)return 'Watch whether the sweep converts into BOS.';
    return 'Wait for a clean Stage-3 liquidity sweep.';
  }
  function watchLevel(s,t){
    if(t?.status==='open')return {title:`Entry ${price(t.entry_price)}`,sub:`SL ${price(t.stop_price)} · TP ${price(t.target_price)}`};
    if(t?.status==='armed')return {title:price(t.entry_price),sub:`Midpoint · POI ${price(t.poi_low)}–${price(t.poi_high)}`};
    if(Number(s?.formation_stage)>=6&&s?.poi_low!=null){const mid=(Number(s.poi_low)+Number(s.poi_high))/2;return {title:price(mid),sub:`POI midpoint · ${price(s.poi_low)}–${price(s.poi_high)}`}}
    return {title:'Not defined yet',sub:Number(s?.formation_stage)>=3?'Wait for BOS and a fresh POI':'No active entry location'};
  }
  function lifecycle(s,t){
    const stage=Number(s?.formation_stage||0),entered=!!t?.entry_at||t?.status==='open'||['win','loss','timeout','ambiguous'].includes(t?.status),poi=stage>=6||!!t;
    return [
      {n:'1',l:'Sweep',d:stage>=3||!!t,c:stage===3||stage===4},
      {n:'2',l:'BOS',d:stage>=5||!!t,c:stage===5},
      {n:'3',l:'POI',d:poi,c:poi&&!entered&&(t?.status!=='armed'?stage===6:true)},
      {n:'4',l:'Entry',d:entered,c:t?.status==='open'}
    ].map(x=>`<div class="focusStep ${x.d?'done':''} ${x.c?'current':''}"><b>${x.n}. ${x.l}</b><span>${x.d?'Reached':'Pending'}</span></div>`).join('');
  }
  function researchContext(t){
    if(!t||t.status!=='armed')return 'Historical revisit context appears after an automatic paper plan is armed.';
    const age=Number(t.pending_age_bars||0),curve=REVISIT[t.symbol]||REVISIT.GBPUSD,next=curve.find(x=>x.b>=age)||curve.at(-1),prev=[...curve].reverse().find(x=>x.b<=age)||null;
    const condition=t.setup_condition==='partially_mitigated'||t.setup_condition==='partially_mitigated_after_target'?' The POI has been partially mitigated, which was materially weaker in the historical proxy.':'';
    if(age>192)return `This plan is beyond the 48-hour studied tail. It remains tracked, but the historical waiting study no longer supports an age-specific claim.${condition}`;
    const lead=prev?`${Math.round(prev.r*100)}% of historical ${t.symbol} candidates had reached midpoint by ${prev.h}h. `:'';
    return `${lead}The next study milestone is ${next.h}h, where ${Math.round(next.r*100)}% had reached midpoint. This is a historical lifecycle base rate, not a forecast for this trade.${condition}`;
  }
  function renderFocus(){
    annotatePairBadges();ensureResearchModelCard();
    const root=document.getElementById('focusBoard');if(!root||typeof state!=='function'||typeof info!=='function')return;
    const s=state(),i=info(),t=currentTrade(),st=statusFor(s,t),wl=watchLevel(s,t),p=i?.brief?.researchPriority?.label||'No focus',pc=planContext(t);
    const age=t?.status==='armed'&&Number.isFinite(Number(t.pending_age_bars))?`${t.pending_age_bars} M15 bars waiting`:`Stage ${s?.formation_stage??'—'}/8`;
    const ctxTitle=pc?.title||currentContextLabel(i),ctxCopy=pc?.detail||`${s?.regime?`Market condition: ${s.regime}. `:''}${t?.setup_condition&&t.setup_condition!=='intact'?`Paper-plan condition: ${t.setup_condition.replaceAll('_',' ')}.`:''}`;
    root.innerHTML=`<section class="focusHero"><div class="focusTop"><div><div class="focusKicker">${safe(selected)} · What matters now</div><div class="focusStatus">${safe(st.label)}</div><div class="focusSummary">${safe(st.summary)}</div></div><span class="focusBadge ${st.tone}">${safe(p)} · ${safe(age)}</span></div><div class="focusLifecycle">${lifecycle(s,t)}</div><div class="focusActions"><button class="focusAction primary" onclick="setView('chartView')">Open chart</button><button class="focusAction" onclick="setView('tradesView')">Paper trade</button></div></section>
    <section class="focusGrid"><article class="focusCard"><div class="label"><span class="material-symbols-rounded">my_location</span>Watch level</div><h3 class="focusLevel">${safe(wl.title)}</h3><p class="focusSubLevel">${safe(wl.sub)}</p></article><article class="focusCard"><div class="label"><span class="material-symbols-rounded">arrow_forward</span>Next trigger</div><h3>What must happen next</h3><p>${safe(nextTrigger(s,t))}</p></article><article class="focusCard"><div class="label"><span class="material-symbols-rounded">layers</span>Context</div><h3>${safe(ctxTitle)}</h3><p>${safe(ctxCopy)}</p></article></section>
    <div class="v15ResearchNote"><strong>Research context:</strong> ${safe(researchContext(t))}</div>`;
  }
  async function loadPaper(){if(loading)return;loading=true;try{const r=await fetch(PAPER_FOCUS,{cache:'no-store'});if(r.ok)fp=await r.json()}catch{}finally{loading=false;renderFocus()}}
  const oldRender=typeof render==='function'?render:null;if(oldRender){render=function(){oldRender();renderFocus()}}
  const oldSet=typeof setView==='function'?setView:null;if(oldSet){setView=function(id){oldSet(id);if(id==='overview')renderFocus();if(id==='evidenceView')ensureResearchModelCard()}}
  renderFocus();loadPaper();setInterval(loadPaper,60_000);
})();
