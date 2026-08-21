(()=>{
  const LAB='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/exit-policy-lab';
  const PAPER='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/paper-trade-engine?symbol=EURUSD,GBPUSD';
  let loading=false,data=null;
  const money=v=>Number.isFinite(Number(v))?`$${Number(v).toFixed(2)}`:'—';
  const n=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):'—';
  const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  function canonicalAccount(trades){
    const clean=(trades||[]).filter(t=>t.entry_at&&['win','loss','timeout'].includes(t.status)&&Number.isFinite(Number(t.gross_r))).sort((a,b)=>new Date(a.entry_at)-new Date(b.entry_at));
    let equity=500;for(const t of clean)equity*=Math.max(.000001,1+.01*Number(t.gross_r));
    return{equity,n:clean.length,totalR:clean.reduce((s,t)=>s+Number(t.gross_r),0),trades:clean};
  }
  function ensure(){
    let root=document.getElementById('v24Policy');if(root)return root;
    root=document.createElement('section');root.id='v24Policy';root.className='v24Policy';
    const chat=document.getElementById('v23Chat'),brief=document.getElementById('v22BriefBoard')||document.getElementById('focusBoard');
    (chat||brief)?.insertAdjacentElement('afterend',root);return root;
  }
  function render(){const root=ensure();if(!root)return;if(!data){root.innerHTML='<div class="v24Loading">Loading the $500 research account…</div>';return}
    const hold=data.lab?.current?.holdSlTp||{},canon=canonicalAccount(data.paper?.trades),excluded=Number(data.lab?.excludedAmbiguousParents||0),pros=(data.lab?.prospectiveAccounts||[]).find(x=>x.policy==='hold_sltp')||{};
    const holdEq=Number(hold.markedEquity),delta=Number.isFinite(holdEq)?holdEq-500:null,canonDelta=canon.equity-500;
    root.innerHTML=`<div class="v24Head"><div><div class="v24Kicker">V2.4 · Account & exit research</div><h3>$500 research account · 1% risk</h3><p>Compare the frozen V2 timeout with your hold-to-SL/TP rule while new exit policies run in shadow.</p></div><span class="v24Risk">Risk scaling OFF</span></div>
      <div class="v24Accounts">
        <article><span>Your rule · hold to SL/TP</span><b>${money(holdEq)}</b><small>${delta==null?'—':`${delta>=0?'+':''}${money(delta).replace('$','$')}`} · ${Number(hold.closed||0)} resolved</small></article>
        <article><span>Canonical V2 · 48-bar timeout</span><b>${money(canon.equity)}</b><small>${canonDelta>=0?'+':''}${money(canonDelta)} · ${canon.n} resolved</small></article>
      </div>
      <div class="v24LiveRows">${canon.trades.slice(-4).map(t=>`<div><span>${safe(t.symbol)} ${safe(String(t.direction).toUpperCase())}</span><b>${Number(t.gross_r)>=0?'+':''}${n(t.gross_r)}R</b><small>${safe(t.status)}</small></div>`).join('')}</div>
      <div class="v24ResearchGrid"><div><span>Historical exit finding</span><b>Hold ≈ 96-bar timeout</b><p>Hold was only slightly ahead of the 48-bar timeout on neutral structural R. No exit rule is promoted because path ambiguity and execution-cost stress still matter.</p></div><div><span>POI depth study</span><b>0–100% shadow grid continues</b><p>The 50% midpoint stays frozen. Earlier apparent depth improvements failed chronological validation, so new depths must earn prospective evidence.</p></div><div><span>Break-even / partials</span><b>Shadow only</b><p>+0.75R break-even looked promising on resolved rows, but too many 5-minute paths were ambiguous. Partial-profit variants have not earned promotion.</p></div><div><span>Risk candidates</span><b>1.5% / 2.0% locked</b><p>A winning streak cannot raise risk. Higher exposure needs at least 100 independent prospective trades, positive stressed expectancy and a drawdown review.</p></div></div>
      <div class="v24Foot"><span>Prospective exit-policy sample after the new freeze: ${Number(pros.n||0)}</span><span>${excluded} canonical ambiguous trade${excluded===1?'':'s'} excluded from account scoring</span></div>`;
  }
  async function load(){if(loading)return;loading=true;try{const [a,b]=await Promise.all([fetch(LAB,{cache:'no-store'}),globalThis.__V2DataBus?.paper?globalThis.__V2DataBus.paper('light'):fetch(PAPER,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`paper ${r.status}`);return r.json()})]);if(!a.ok)throw new Error(`policy ${a.status}`);data={lab:await a.json(),paper:b};render()}catch(e){console.warn('V2.4 policy',e);const r=ensure();if(r&&!data)r.innerHTML='<div class="v24Error">Account research is temporarily unavailable. The underlying paper engine is unchanged.</div>'}finally{loading=false}}
  ensure();render();load();setInterval(()=>{if(!document.hidden)load()},60_000);
})();
