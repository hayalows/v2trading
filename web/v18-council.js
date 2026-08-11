(()=>{
  const URL='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/model-council';
  let council=null,loading=false;
  const safe=v=>typeof esc==='function'?esc(v):String(v??'');
  const n=v=>Number.isFinite(Number(v))?Number(v).toLocaleString():'—';
  const pct=v=>Number.isFinite(Number(v))?`${(Number(v)*100).toFixed(1)}%`:'—';
  function decisionCopy(x){
    if(x==='historical_candidate')return 'Historical gate passed · live influence withheld';
    if(x==='shadow')return 'Shadow only · hidden prospective scoring';
    if(x==='rejected')return 'Rejected by frozen gate';
    if(x==='baseline')return 'Frozen comparator';
    if(x==='not_run')return 'Frozen run pending';
    return String(x||'Unknown');
  }
  function stateCopy(x){
    if(x==='MODEL_DISAGREEMENT')return 'Models disagree materially';
    if(x==='LOW_DISAGREEMENT')return 'Models broadly agree';
    return 'No eligible dual score yet';
  }
  function ensure(){
    const view=document.getElementById('evidenceView');if(!view)return null;
    let card=document.getElementById('modelCouncilResearch');
    if(!card){card=document.createElement('article');card.id='modelCouncilResearch';card.className='card modelCouncilResearch';const shadow=document.getElementById('shadowArenaResearch');if(shadow)shadow.insertAdjacentElement('afterend',card);else view.querySelector('.stats')?.insertAdjacentElement('afterend',card)}
    return card;
  }
  function render(){
    const card=ensure();if(!card)return;
    if(!council){card.innerHTML='<div class="cardLabel"><span class="material-symbols-rounded">hub</span>Model Council</div><h3>Loading model-selection evidence…</h3>';return}
    const d=council.decisions||{},p=council.prospective||{},latest=p.latest||{};
    card.innerHTML=`<div class="councilHead"><div><div class="cardLabel"><span class="material-symbols-rounded">hub</span>V2 Model Council v1.8</div><h3>Make models compete, then measure when they disagree.</h3><p>StateTwin, its deployable student and Granite TTM are evaluated on the same independent campaigns. The browser receives model status and qualitative disagreement only; live probabilities remain server-side.</p></div><span class="councilBoundary">PROBABILITY WITHHELD</span></div>
      <div class="councilGrid">
        <div><span>Eligible age-0 records</span><b>${n(p.eligibleRecords)}</b><small>Later campaign landmarks are not scored by age-0 models.</small></div>
        <div><span>Dual scored</span><b>${n(p.bothScored)}</b><small>StateTwin student and TTM both scored before outcome.</small></div>
        <div><span>Resolved dual scores</span><b>${n(p.resolvedBoth)}</b><small>Prospective observations available for calibration.</small></div>
        <div><span>Disagreement rate</span><b>${pct(p.disagreementRate)}</b><small>Absolute hidden probability gap ≥ 0.15.</small></div>
      </div>
      <div class="councilDecisions">
        <div class="councilDecision"><span>Historical Council</span><b>${safe(decisionCopy(d.council))}</b><small>Must beat both parents and pass the paired bootstrap.</small></div>
        <div class="councilDecision"><span>StateTwin student</span><b>${safe(decisionCopy(d.stateTwinStudent))}</b><small>Compact scorer must remain close to the original teacher.</small></div>
        <div class="councilDecision"><span>Granite TTM</span><b>${safe(decisionCopy(d.graniteTtm))}</b><small>Age-0 structural challenger only. No trade or Focus influence.</small></div>
      </div>
      <div class="councilState"><div><b>Latest eligible council state</b><span>${latest.symbol?`${safe(latest.symbol)} ${safe(latest.direction||'')} · ${safe(latest.observedAt||'')}`:'Waiting for the first eligible age-0 record.'}</span></div><strong>${safe(stateCopy(latest.qualitativeState))}</strong></div>
      <div class="councilFoot"><strong>Research boundary:</strong> ${safe(council.boundary||'No current probability is exposed.')}${council.calibration?.suppressed?` Aggregate prospective calibration stays suppressed until ${n(council.calibration.unlockAt)} resolved dual-scored records.`:''}</div>`;
  }
  async function load(){if(loading)return;loading=true;try{const r=await fetch(URL,{cache:'no-store'});if(!r.ok)throw new Error('Model Council unavailable');council=await r.json();render()}catch(e){console.warn('Model Council',e)}finally{loading=false}}
  const oldSet=typeof setView==='function'?setView:null;if(oldSet){setView=function(id){oldSet(id);if(id==='evidenceView'){render();load()}}}
  load();setInterval(load,60_000);
})();
