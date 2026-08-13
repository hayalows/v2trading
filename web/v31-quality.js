(()=>{
  const URL='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/trade-quality?symbol=EURUSD,GBPUSD';
  let data=null,loading=false,lastLoad=0;
  const $=(s,r=document)=>r.querySelector(s);
  const pair=()=>{try{return typeof selected!=='undefined'?selected:$('.pairBtn.active')?.dataset.pair||'EURUSD'}catch{return $('.pairBtn.active')?.dataset.pair||'EURUSD'}};
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const f1=v=>Number.isFinite(Number(v))?Number(v).toFixed(1):'—';
  const pct=v=>Number.isFinite(Number(v))?`${Number(v).toFixed(1)}%`:'—';
  function model(){const s=pair();return {symbol:s,current:data?.current?.[s]||null,stats:data?.winRate||null,hist:data?.historicalInteractionEvidence||null}}
  function floorText(c){
    if(!c?.risk)return '';
    if(c.risk.stopPolicyVersion==='v3.0_breathing_room')return c.risk.floorApplied?`Minimum breathing room applied: ${f1(c.risk.pips)} pips.`:`Structural stop was already wider than the ${f1(c.risk.floorPips)}-pip minimum.`;
    return 'This plan was created before the new breathing-room rule and remains frozen under its original stop.';
  }
  function attentionText(c){const a=c?.fastAttention;if(!a||!['IN_ZONE','VERY_NEAR','NEAR'].includes(a.status))return '';return a.status==='IN_ZONE'?`Live watch: price is inside the entry zone, about ${f1(a.distanceToEntryPips)} pips from the midpoint.`:`Live watch: price is about ${f1(a.distanceToEntryPips)} pips from the midpoint.`;}
  function frictionText(c){const f=c?.friction;if(!f||!['HIGH','ELEVATED'].includes(f.status))return '';return `Price friction is ${f.status.toLowerCase()}: the indicative spread is about ${f1(f.indicativeSpreadPips)} pips (${f1(f.spreadAsPctOfRisk)}% of the stop distance).`;}
  function details(m){
    const s=m.stats,h=m.hist;if(!s&&!h)return '';
    const live=s?`<div><b>Live journal</b><span>${pct(s.decisiveWinRatePct)} decisive win rate · ${pct(s.scoredClosureWinSharePct)} when numeric timeouts are included. ${s.wins} win, ${s.losses} losses, ${s.timeouts} timeout, ${s.ambiguous} ambiguous.</span></div>`:'';
    const hist=h?`<div><b>Why first interaction matters</b><span>In the 2022–2025 historical study, direct first-interaction entries won ${pct(h.directFirstInteraction?.winRatePct)} versus ${pct(h.priorShallowTouch?.winRatePct)} after an earlier shallow touch. This is historical context, not a probability for this trade.</span></div>`:'';
    return `<details class="v31Details"><summary>Why this grade?</summary><div class="v31DetailsBody">${live}${hist}<div><b>Boundary</b><span>V2 does not know that a trade will win. The grade only describes setup quality from information already observed.</span></div></div></details>`;
  }
  function cardHTML(m,compact=false){
    const c=m.current,q=c?.quality||{code:'NO_SETUP',label:'No setup to grade',tone:'neutral',reason:'V2 is waiting for a mature setup.',next:'Wait for the normal setup sequence.'};
    const risk=floorText(c),att=attentionText(c),friction=frictionText(c);
    return `<div class="v31QualityHead"><div><span>Setup quality</span><strong>${esc(q.label)}</strong></div><span class="v31QualityBadge ${esc(q.tone)}">${esc(m.symbol)}</span></div><p>${esc(q.reason)}</p>${att?`<p class="v31QualityLive">${esc(att)}</p>`:''}${risk?`<p class="v31QualityNote">${esc(risk)}</p>`:''}${friction?`<p class="v31QualityWarn">${esc(friction)}</p>`:''}${!compact?`<div class="v31Next"><b>What now</b><span>${esc(q.next)}</span></div>${details(m)}`:''}`;
  }
  function renderHome(){const root=$('#focusBoard');if(!root)return;const m=model(),sig=JSON.stringify([m.symbol,m.current?.tradeKey,m.current?.quality?.code,m.current?.risk?.pips,m.current?.fastAttention?.status,m.current?.fastAttention?.distanceToEntryPips,m.stats?.wins,m.stats?.losses,m.stats?.timeouts]);let card=$('#v31SetupQuality',root);if(!card){card=document.createElement('article');card.id='v31SetupQuality';card.className='v31QualityCard';root.querySelector('.focusHero')?.insertAdjacentElement('afterend',card)}if(card&&card.dataset.sig!==sig){card.dataset.sig=sig;card.innerHTML=cardHTML(m)}}
  function renderTrade(){const host=$('#paperCurrent');if(!host)return;const m=model(),c=m.current;if(!c||!c.tradeKey){$('#v31TradeQuality',host)?.remove();return}const sig=JSON.stringify([m.symbol,c.tradeKey,c.quality?.code,c.risk?.pips,c.friction?.status,c.fastAttention?.status,c.fastAttention?.distanceToEntryPips]);let card=$('#v31TradeQuality',host);if(!card){card=document.createElement('div');card.id='v31TradeQuality';card.className='v31TradeQuality';host.prepend(card)}if(card.dataset.sig!==sig){card.dataset.sig=sig;card.innerHTML=cardHTML(m,true)}}
  function render(){if(!data)return;renderHome();renderTrade()}
  async function load(force=false){if(loading)return;if(!force&&Date.now()-lastLoad<20000){render();return}loading=true;try{const r=await fetch(URL,{cache:'no-store'});if(r.ok){data=await r.json();window.v31SetupQuality=data;lastLoad=Date.now();render()}}catch{}finally{loading=false}}
  let timer=null;const schedule=()=>{clearTimeout(timer);timer=setTimeout(render,30)};
  const focus=$('#focusBoard');if(focus)new MutationObserver(schedule).observe(focus,{childList:true});
  const paper=$('#paperCurrent');if(paper)new MutationObserver(schedule).observe(paper,{childList:true});
  document.addEventListener('click',e=>{if(e.target.closest?.('[data-pair]'))setTimeout(()=>{render();load(true)},60)});
  document.addEventListener('DOMContentLoaded',()=>load(true));
  load(true);setInterval(()=>load(true),60000);
})();
