(()=>{
  const URL='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/shadow-arena';
  let arena=null,loading=false;
  const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
  const pct=(v,d=1)=>Number.isFinite(Number(v))?`${(Number(v)*100).toFixed(d)}%`:'—';
  const safe=v=>typeof esc==='function'?esc(v):String(v??'');
  function statusCopy(m){
    if(m.status==='baseline')return 'Frozen comparator';
    if(m.status==='historical_candidate')return 'Passed historical gate · live probability withheld';
    if(m.status==='challenger')return 'Research challenger · zero product influence';
    if(m.status==='shadow')return 'Passed frozen historical gate · prospective shadow only';
    if(m.status==='promoted')return 'Prospective gate passed';
    if(m.status==='rejected')return 'Rejected by frozen gate';
    return String(m.status||'research');
  }
  function ensure(){
    const view=document.getElementById('evidenceView');if(!view)return null;
    let card=document.getElementById('shadowArenaResearch');
    if(!card){card=document.createElement('article');card.id='shadowArenaResearch';card.className='card shadowArenaResearch';const twin=document.getElementById('stateTwinResearch');if(twin)twin.insertAdjacentElement('afterend',card);else view.querySelector('.stats')?.insertAdjacentElement('afterend',card)}
    return card;
  }
  function render(){
    const card=ensure();if(!card)return;
    if(!arena){card.innerHTML='<div class="cardLabel"><span class="material-symbols-rounded">visibility</span>Prospective Shadow Arena</div><h3>Loading pre-outcome calibration records…</h3>';return}
    const c=arena.counts||{},cal=arena.calibration||{},models=arena.models||[];
    const modelHtml=models.map(m=>`<div class="shadowModel"><div><b>${safe(m.model_family)}</b><span>${safe(m.model_version)}</span></div><small>${safe(statusCopy(m))}</small></div>`).join('');
    const latest=(arena.latest||[]).slice(0,4).map(x=>`<li><b>${safe(x.symbol)} ${safe(x.direction)}</b> · age ${safe(x.landmark_age_bars)} · ${safe(x.status)}${x.outcome===1?' · BOS reached':x.outcome===0?' · no BOS in horizon':''}</li>`).join('');
    card.innerHTML=`<div class="shadowHead"><div><div class="cardLabel"><span class="material-symbols-rounded">visibility</span>V2 Shadow Arena v1.7</div><h3>Make the models predict before the market answers.</h3><p>Each qualifying Stage-3/4 landmark is frozen with its exact market state before the next 16 completed M15 bars unfold. Outcomes are resolved automatically. Model probabilities stay hidden while calibration is being earned.</p></div><span class="shadowAbstain">ABSTAIN</span></div>
      <div class="shadowGrid">
        <div><span>Pending</span><b>${n(c.pending)}</b><small>Forecasts whose outcome is still unknown</small></div>
        <div><span>Resolved</span><b>${n(c.resolved)}</b><small>True prospective labels</small></div>
        <div><span>Observed BOS rate</span><b>${pct(cal.observedEventRate)}</b><small>Descriptive only while the sample is small</small></div>
        <div><span>Base Brier</span><b>${n(cal.baselineBrier,4)}</b><small>Frozen ${pct(cal.baselineProbability)} walk-forward comparator</small></div>
      </div>
      <div class="shadowModels">${modelHtml}</div>
      <div class="shadowFoot"><strong>${c.total?`${n(c.total)} immutable forecast record${Number(c.total)===1?'':'s'} collected.`:'Waiting for the next qualifying Stage-3/4 landmark.'}</strong><span>Granite TTM R2 passed its frozen standalone historical gate, but it still needs prospective scoring and must prove incremental value beyond StateTwin before it can influence Focus.</span>${latest?`<ul>${latest}</ul>`:''}</div>`;
  }
  async function load(){if(loading)return;loading=true;try{const r=await fetch(URL,{cache:'no-store'});if(!r.ok)throw new Error('Shadow Arena unavailable');arena=await r.json();render()}catch(e){console.warn('Shadow Arena',e)}finally{loading=false}}
  function loadV18(){
    if(!document.querySelector('link[data-v18-council]')){const l=document.createElement('link');l.rel='stylesheet';l.href='/v18.css';l.dataset.v18Council='1';document.head.appendChild(l)}
    if(!document.querySelector('script[data-v18-council]')){const s=document.createElement('script');s.src='/v18-council.js';s.dataset.v18Council='1';s.defer=true;document.body.appendChild(s)}
  }
  function loadV20(){
    if(!document.querySelector('link[data-v20-poi]')){const l=document.createElement('link');l.rel='stylesheet';l.href='/v20.css';l.dataset.v20Poi='1';document.head.appendChild(l)}
    if(!document.querySelector('script[data-v20-poi]')){const s=document.createElement('script');s.src='/v20-poi-learning.js';s.dataset.v20Poi='1';s.defer=true;document.body.appendChild(s)}
  }
  const oldSet=typeof setView==='function'?setView:null;if(oldSet){setView=function(id){oldSet(id);if(id==='evidenceView'){render();load()}}}
  load();setInterval(load,60_000);loadV18();loadV20();
})();
