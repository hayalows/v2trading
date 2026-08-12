(()=>{
  const escx=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=(v,d=2)=>v===null||v===undefined||!Number.isFinite(Number(v))?'—':Number(v).toFixed(d);
  const when=t=>t?new Date(t).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'—';
  const label=s=>String(s||'unavailable').replaceAll('_',' ').replace(/\b\w/g,x=>x.toUpperCase());
  function qualityCopy(q){
    if(!q||q.status==='UNAVAILABLE')return 'No BID/ASK microstructure sample is available yet.';
    const fresh=q.status==='STALE'?`Stale · last sample ${num(q.ageMinutes,0)} min ago`:q.status;
    return `${fresh} · spread ${num(q.spreadMeanPips,2)} pips (${num(q.spreadVsMedian,2)}× recent median) · ${q.activity} tick activity (${num(q.ticksPerMinute,0)} ticks/min).`;
  }
  function executionCopy(a){
    if(!a)return 'No independent execution audit has been recorded for this trade yet.';
    const conf=a.details?.confidence==='tick'?'Exact public BID/ASK tick path':a.details?.confidence==='1m'?'Public BID/ASK 1-minute path':'Execution path unavailable';
    if(a.entry_confirmed===true)return `${conf} independently confirms the entry${a.entry_at_tick?` at ${when(a.entry_at_tick)}`:''}${Number.isFinite(Number(a.entry_spread_pips))?` with about ${num(a.entry_spread_pips,2)} pip indicative spread`:''}. Canonical P&L is unchanged.`;
    if(a.shadow_outcome&&a.shadow_outcome!=='not_filled')return `${conf} shadow outcome: ${label(a.shadow_outcome)}. This does not rewrite the canonical $500 journal.`;
    if(a.entry_confirmed===false&&a.details?.confidence&&a.details.confidence!=='none')return `${conf} did not reproduce the canonical entry. Treat this as an execution-consistency warning; historical P&L remains frozen.`;
    return 'Independent BID/ASK execution evidence was unavailable. The canonical research result remains unchanged.';
  }
  function renderDataCard(data){
    const view=document.getElementById('dataView');if(!view)return;
    let card=document.getElementById('v27ExecutionQuality');if(!card){card=document.createElement('article');card.className='card';card.id='v27ExecutionQuality';const head=view.querySelector('.sectionHead');head?.insertAdjacentElement('afterend',card)}
    const q=data.marketQuality||{};
    card.innerHTML=`<div class="cardLabel"><span class="material-symbols-rounded">ssid_chart</span>BID/ASK microstructure</div><h3>Execution context is now tracked separately from setup quality.</h3><p><strong>EURUSD:</strong> ${escx(qualityCopy(q.EURUSD))}</p><p style="margin-top:8px"><strong>GBPUSD:</strong> ${escx(qualityCopy(q.GBPUSD))}</p><div class="paperNotice"><strong>Boundary</strong>Dukascopy BID/ASK ticks are public indicative market data, not broker-specific executable fills. V2 uses them as shadow execution evidence only.</div>`;
  }
  function renderAccountEvidence(data){
    const root=document.getElementById('paperAccount'),a=data.account;if(!root||!a)return;
    let x=root.querySelector('[data-v27-account]');if(!x){x=document.createElement('div');x.className='paperNotice';x.dataset.v27Account='1';root.appendChild(x)}
    const confirmed=a.executionConfirmedEntries??a.tickConfirmedEntries??0,audited=a.executionAudited??0;
    x.innerHTML=`<strong>Execution audit</strong>${confirmed} of ${audited} audited historical entries currently have independent BID/ASK confirmation. This audit is shadow-only and does not change the balance.`;
  }
  function renderTradeEvidence(data){
    const by=new Map((data.tradeMetrics||[]).map(x=>[x.tradeKey,x]));
    document.querySelectorAll('.tradeRow[data-trade-key]').forEach(row=>{const m=by.get(row.dataset.tradeKey);if(!m)return;let box=row.querySelector('[data-v27-exec]');if(!box){box=document.createElement('div');box.className='paperNotice';box.dataset.v27Exec='1';row.appendChild(box)}const q=data.marketQuality?.[m.symbol],a=m.executionAudit;box.innerHTML=`<strong>Execution evidence · ${escx(a?.details?.confidence==='tick'?'TICK':a?.details?.confidence==='1m'?'1-MINUTE':'UNVERIFIED')}</strong>${escx(executionCopy(a))}${q?` <span style="opacity:.8">Recent ${escx(m.symbol)} context: ${escx(qualityCopy(q))}</span>`:''}`});
  }
  let sig='';
  function render(){const data=window.v2PaperAccount;if(!data?.account)return;const next=`${data.generatedAt||''}:${data.account.executionAudited||0}:${data.marketQuality?.EURUSD?.asOf||''}:${data.marketQuality?.GBPUSD?.asOf||''}`;if(next===sig&&document.getElementById('v27ExecutionQuality'))return;sig=next;renderDataCard(data);renderAccountEvidence(data);renderTradeEvidence(data)}
  const mo=new MutationObserver(()=>render());mo.observe(document.documentElement,{subtree:true,childList:true});
  render();setInterval(render,5000);
})();