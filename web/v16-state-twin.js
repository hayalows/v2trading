(()=>{
  const STATE_TWIN='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/state-twin?symbol=EURUSD,GBPUSD';
  let twin={pairs:[]},loading=false;
  const safe=v=>typeof esc==='function'?esc(v):String(v??'');
  const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
  const pct=(v,d=0)=>Number.isFinite(Number(v))?`${(Number(v)*100).toFixed(d)}%`:'—';
  const pair=()=>twin.pairs?.find(x=>x.symbol===selected)||null;
  const tone=x=>x==='unstable'||x==='high'?'bad':x==='transitioning'||x==='elevated'?'warn':'good';
  function analogCopy(a){
    if(!a)return {value:'Building',sub:'Comparable-state layer is loading.'};
    if(a.weightedRate!=null)return {value:pct(a.weightedRate),sub:`Descriptive ${a.target} rate within ${a.horizonHours}h · effective n ${n(a.effectiveN,1)}.`};
    const similarity=Number.isFinite(Number(a.similarityScore))?`${n(a.similarityScore)} / 100`:'Building';
    return {value:similarity,sub:`Nearest-state similarity only · ${a.candidateEpisodes??0} de-correlated live episodes found. Outcome probability stays hidden until the multi-year gate passes.`};
  }
  function stabilityCopy(x){
    if(!x)return 'Loading regime-change diagnostics.';
    const mass=x.recentBreakMass==null?'—':pct(x.recentBreakMass,1),run=Number.isFinite(Number(x.expectedRunBars))?`${n(x.expectedRunBars)} bars`:'—';
    return `Short-run posterior mass ${mass} · estimated current run ${run} · volatility ratio ${n(x.volatilityRatio,2)}×.`;
  }
  function renderTwin(){
    const root=document.getElementById('focusBoard'),x=pair();if(!root||!x)return;
    let card=document.getElementById('stateTwinCard');if(!card){card=document.createElement('section');card.id='stateTwinCard';card.className='stateTwinCard';const note=root.querySelector('.v15ResearchNote');if(note)root.insertBefore(card,note);else root.appendChild(card)}
    const a=analogCopy(x.analog),c=x.crossPair||{},changes=(x.whatChanged||[]).map(v=>`<li>${safe(v)}</li>`).join('');
    card.innerHTML=`<div class="stateTwinHead"><div><div class="stateTwinKicker"><span class="material-symbols-rounded">neurology</span>StateTwin intelligence</div><h3>${safe(x.mode?.label||'Market state loading')}</h3><p>Structural state, regime-break pressure and cross-pair context. Research intelligence, not a buy/sell instruction.</p></div><span class="stateTwinPill ${tone(x.stability?.label)}">${safe(x.stability?.label||'loading')}</span></div>
      <div class="stateTwinGrid">
        <article><span>State coherence</span><b>${n(x.mode?.coherenceScore)} / 100</b><small>${safe(x.mode?.higherTimeframeBias||'mixed')} higher-timeframe bias</small></article>
        <article><span>Regime stability</span><b>${safe(x.stability?.label||'—')}</b><small>${safe(stabilityCopy(x.stability))}</small></article>
        <article><span>Comparable states</span><b>${safe(a.value)}</b><small>${safe(a.sub)}</small></article>
        <article><span>Cross-pair structure</span><b>${c.correlation8h==null?'—':n(c.correlation8h,2)}</b><small>${safe(c.interpretation||'EURUSD/GBPUSD relationship is loading.')}</small></article>
      </div>
      <div class="stateTwinChanges"><div><span class="material-symbols-rounded">difference</span><strong>What changed</strong></div><ul>${changes||'<li>No large state change recorded.</li>'}</ul></div>`;
    ensureResearchCard();
  }
  function ensureResearchCard(){
    const view=document.getElementById('evidenceView');if(!view||document.getElementById('stateTwinResearch'))return;
    const card=document.createElement('article');card.id='stateTwinResearch';card.className='card stateTwinResearch';card.style.marginTop='12px';
    card.innerHTML='<div class="cardLabel"><span class="material-symbols-rounded">neurology</span>V2 StateTwin v1.6</div><h3>Predict structural transitions, not the next candle.</h3><p>The live layer combines the existing multi-timeframe V2 state with a Bayesian online run-length model, de-correlated state similarity and EURUSD/GBPUSD co-movement. Comparable states can be shown now, but outcome probability stays withheld until the preregistered multi-year walk-forward gate passes.</p><div class="v15ResearchNote"><strong>Foundation-model policy:</strong> Chronos-2/Chronos-Bolt, TimesFM, MOMENT and patch/representation models remain challenger models. They only enter the live stack if walk-forward testing improves calibration beyond the simpler structural baseline. The earlier broker-execution failure still blocks live-money claims.</div>';
    const model=document.getElementById('v15RevisitModel');if(model)model.insertAdjacentElement('afterend',card);else view.querySelector('.stats')?.insertAdjacentElement('afterend',card);
  }
  async function loadTwin(){if(loading)return;loading=true;try{const r=await fetch(STATE_TWIN,{cache:'no-store'});if(!r.ok)throw new Error('StateTwin unavailable');twin=await r.json();renderTwin()}catch(e){console.warn('StateTwin',e)}finally{loading=false}}
  const oldRender=typeof render==='function'?render:null;if(oldRender){render=function(){oldRender();renderTwin()}}
  const oldSet=typeof setView==='function'?setView:null;if(oldSet){setView=function(id){oldSet(id);if(id==='overview')renderTwin();if(id==='evidenceView')ensureResearchCard()}}
  loadTwin();setInterval(loadTwin,60_000);
})();