(()=>{
  const escx=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=(v,d=2)=>v===null||v===undefined||!Number.isFinite(Number(v))?'—':Number(v).toFixed(d);
  const when=t=>t?new Date(t).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'—';
  const label=s=>String(s||'unavailable').replaceAll('_',' ').replace(/\b\w/g,x=>x.toUpperCase());
  const mobile=()=>window.matchMedia('(max-width:719px)').matches;
  function qualityCopy(q){
    if(!q||q.status==='UNAVAILABLE')return 'No separate BID/ASK sample is available yet.';
    const fresh=q.status==='STALE'?`Stale · last sample ${num(q.ageMinutes,0)} min ago`:q.status;
    return `${fresh} · spread ${num(q.spreadMeanPips,2)} pips (${num(q.spreadVsMedian,2)}× recent median) · ${q.activity} tick activity (${num(q.ticksPerMinute,0)} ticks/min).`;
  }
  function executionCopy(a){
    if(!a)return {plain:'No separate price check is available for this trade yet.',technical:'The independent BID/ASK audit has not recorded evidence for this trade.'};
    const conf=a.details?.confidence==='tick'?'exact public BID/ASK ticks':a.details?.confidence==='1m'?'public BID/ASK 1-minute prices':'separate price path';
    if(a.entry_confirmed===true)return {plain:'A separate public price feed also reached this paper entry. This supports the recorded entry, but it is not a broker fill.',technical:`Checked with ${conf}${a.entry_at_tick?` at ${when(a.entry_at_tick)}`:''}${Number.isFinite(Number(a.entry_spread_pips))?` · indicative spread about ${num(a.entry_spread_pips,2)} pips`:''}. The paper result is unchanged.`};
    if(a.shadow_outcome&&a.shadow_outcome!=='not_filled')return {plain:'The separate price check found a different research outcome. V2 keeps the paper account unchanged.',technical:`${conf} shadow outcome: ${label(a.shadow_outcome)}. This does not rewrite the $500 journal.`};
    if(a.entry_confirmed===false&&a.details?.confidence&&a.details.confidence!=='none')return {plain:'A separate public price feed did not show the same paper entry. Treat this as a research warning, not a correction to the account.',technical:`${conf} did not reproduce the recorded entry. Historical paper P&L remains frozen.`};
    return {plain:'The separate price check was unavailable, so V2 keeps the original paper result unchanged.',technical:'Independent BID/ASK evidence was unavailable.'};
  }
  function renderDataCard(data){
    const view=document.getElementById('dataView');if(!view)return;
    let card=document.getElementById('v27ExecutionQuality');const q=data.marketQuality||{};
    if(mobile()){
      if(!card||card.tagName!=='DETAILS'){card?.remove();card=document.createElement('details');card.className='card v27Advanced';card.id='v27ExecutionQuality';view.querySelector('.sectionHead')?.insertAdjacentElement('afterend',card)}
      const html=`<summary><span><strong>Extra price data</strong><small>Advanced research check — optional</small></span><span class="material-symbols-rounded">expand_more</span></summary><div class="v27AdvancedBody"><p>V2 keeps a second public BID/ASK price feed for research. You do not need this to understand the normal setup or paper trade.</p><p><strong>EURUSD:</strong> ${escx(qualityCopy(q.EURUSD))}</p><p><strong>GBPUSD:</strong> ${escx(qualityCopy(q.GBPUSD))}</p><p class="v27Boundary">This is public market data, not your broker's exact fill, spread or slippage.</p></div>`;if(card.innerHTML!==html)card.innerHTML=html;
    }else{
      if(!card||card.tagName==='DETAILS'){card?.remove();card=document.createElement('article');card.className='card';card.id='v27ExecutionQuality';view.querySelector('.sectionHead')?.insertAdjacentElement('afterend',card)}
      const html=`<div class="cardLabel"><span class="material-symbols-rounded">ssid_chart</span>BID/ASK microstructure</div><h3>Execution context is tracked separately from setup quality.</h3><p><strong>EURUSD:</strong> ${escx(qualityCopy(q.EURUSD))}</p><p style="margin-top:8px"><strong>GBPUSD:</strong> ${escx(qualityCopy(q.GBPUSD))}</p><div class="paperNotice"><strong>Boundary</strong>Public BID/ASK data is research evidence, not broker-specific execution.</div>`;if(card.innerHTML!==html)card.innerHTML=html;
    }
  }
  function renderAccountEvidence(data){
    const root=document.getElementById('paperAccount'),a=data.account;if(!root||!a)return;let x=root.querySelector('[data-v27-account]');const confirmed=a.executionConfirmedEntries??a.tickConfirmedEntries??0,audited=a.executionAudited??0;
    if(mobile()){
      if(!x||x.tagName!=='DETAILS'){x?.remove();x=document.createElement('details');x.className='v27Advanced';x.dataset.v27Account='1';root.appendChild(x)}
      const html=`<summary><span>Advanced account checks</span><span class="material-symbols-rounded">expand_more</span></summary><div class="v27AdvancedBody"><p>This is an optional research quality check. It does not change your balance.</p><p>${confirmed} of ${audited} historical paper entries currently have separate BID/ASK confirmation.</p></div>`;if(x.innerHTML!==html)x.innerHTML=html;
    }else{
      if(!x||x.tagName==='DETAILS'){x?.remove();x=document.createElement('div');x.className='paperNotice';x.dataset.v27Account='1';root.appendChild(x)}
      const html=`<strong>Execution audit</strong>${confirmed} of ${audited} audited historical entries currently have independent BID/ASK confirmation. This audit is shadow-only and does not change the balance.`;if(x.innerHTML!==html)x.innerHTML=html;
    }
  }
  function renderTradeEvidence(data){
    const by=new Map((data.tradeMetrics||[]).map(x=>[x.tradeKey,x]));
    document.querySelectorAll('.tradeRow[data-trade-key]').forEach(row=>{const m=by.get(row.dataset.tradeKey);if(!m)return;let box=row.querySelector('[data-v27-exec]'),q=data.marketQuality?.[m.symbol],a=m.executionAudit,c=executionCopy(a);
      if(mobile()){
        if(!box||box.tagName!=='DETAILS'){box?.remove();box=document.createElement('details');box.className='v27Advanced tradeExecution';box.dataset.v27Exec='1';row.appendChild(box)}
        const html=`<summary><span>Extra price check</span><span class="material-symbols-rounded">expand_more</span></summary><div class="v27AdvancedBody"><p>${escx(c.plain)}</p><p class="v27Technical">${escx(c.technical)}${q?` Recent ${escx(m.symbol)} data: ${escx(qualityCopy(q))}`:''}</p></div>`;if(box.innerHTML!==html)box.innerHTML=html;
      }else{
        if(!box||box.tagName==='DETAILS'){box?.remove();box=document.createElement('div');box.className='paperNotice';box.dataset.v27Exec='1';row.appendChild(box)}const html=`<strong>Execution evidence</strong>${escx(c.technical)}${q?` <span style="opacity:.8">Recent ${escx(m.symbol)} context: ${escx(qualityCopy(q))}</span>`:''}`;if(box.innerHTML!==html)box.innerHTML=html;
      }
    });
  }
  function surfacesIntact(){if(!document.getElementById('v27ExecutionQuality')||!document.querySelector('#paperAccount [data-v27-account]'))return false;const rows=[...document.querySelectorAll('.tradeRow[data-trade-key]')];if(!rows.length)return true;return rows.every(r=>r.querySelector('[data-v27-exec]'))}
  let sig='';function render(){const data=window.v2PaperAccount;if(!data?.account)return;const next=`${data.generatedAt||''}:${data.account.executionAudited||0}:${data.marketQuality?.EURUSD?.asOf||''}:${data.marketQuality?.GBPUSD?.asOf||''}:${mobile()}`;if(next===sig&&surfacesIntact())return;sig=next;renderDataCard(data);renderAccountEvidence(data);renderTradeEvidence(data)}
  const mo=new MutationObserver(()=>render());mo.observe(document.documentElement,{subtree:true,childList:true});window.matchMedia('(max-width:719px)').addEventListener?.('change',()=>{sig='';render()});render();setInterval(render,5000);
})();