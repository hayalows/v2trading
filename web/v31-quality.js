(()=>{
  if(globalThis.__v31QualityLoaded)return;globalThis.__v31QualityLoaded=true;
  const URL='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/trade-quality?symbol=EURUSD,GBPUSD';
  let data=null,loading=false,lastLoad=0;
  const $=(s,r=document)=>r.querySelector(s);
  const pair=()=>{try{return typeof selected!=='undefined'?selected:$('.pairBtn.active')?.dataset.pair||'EURUSD'}catch{return $('.pairBtn.active')?.dataset.pair||'EURUSD'}};
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const f1=v=>Number.isFinite(Number(v))?Number(v).toFixed(1):'—';
  const f5=v=>Number.isFinite(Number(v))?Number(v).toFixed(5):'—';
  const pct=v=>Number.isFinite(Number(v))?`${Number(v).toFixed(1)}%`:'—';
  const cap=s=>String(s??'mixed').replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
  const age=t=>{const x=new Date(t||0).getTime();if(!x)return null;return Math.max(0,(Date.now()-x)/60000)};
  function model(){const s=pair();return {symbol:s,current:data?.current?.[s]||null,stats:data?.winRate||null,hist:data?.historicalInteractionEvidence||null,v34:data?.v34Evidence||null}}
  function floorText(c){
    if(!c?.risk)return '';
    if(c.risk.stopPolicyVersion==='v3.0_breathing_room')return c.risk.floorApplied?`Minimum breathing room applied: ${f1(c.risk.pips)} pips.`:`Structural stop was already wider than the ${f1(c.risk.floorPips)}-pip minimum.`;
    return 'This plan was created before the new breathing-room rule and remains frozen under its original stop.';
  }
  function attentionText(c){const a=c?.fastAttention;if(!a||!['IN_ZONE','VERY_NEAR','NEAR'].includes(a.status))return '';return a.status==='IN_ZONE'?`Live watch: price is inside the entry zone, about ${f1(a.distanceToEntryPips)} pips from the midpoint.`:`Live watch: price is about ${f1(a.distanceToEntryPips)} pips from the midpoint.`;}
  function frictionText(c){const f=c?.friction;if(!f||!['HIGH','ELEVATED'].includes(f.status))return '';return `Price friction is ${f.status.toLowerCase()}: the indicative spread is about ${f1(f.indicativeSpreadPips)} pips (${f1(f.spreadAsPctOfRisk)}% of the stop distance).`;}
  function levelText(x){if(!x)return 'No mapped level';const side=x.side==='buy_side'?'Buy-side':'Sell-side',state=String(x.status||'').replaceAll('_',' ');return `${side} ${x.kind} ${f5(x.level)} · ${f1(x.distancePips)} pips · ${state}`;}
  function mapStrip(c){
    const i=c?.marketIntelligence;if(!i)return '';
    const st=i.structure||{},w=i.rangeLocation?.currentWeekCompleted,a=age(i.generatedAt),fresh=a==null?'Map active':`Map ${a<1?'<1':Math.round(a)}m ago`;
    const chips=[`M15 ${cap(st.m15)}`,`H4 ${cap(st.h4)}`,`D1 ${cap(st.d1)}`,`W1 ${cap(st.w1)}`,w?.zone?`Week ${cap(w.zone)}`:null,fresh].filter(Boolean);
    return `<div class="v34MapStrip" aria-label="V3.4 market map">${chips.map((x,j)=>`<span${j===chips.length-1?' class="v34Fresh"':''}>${esc(x)}</span>`).join('')}</div>`;
  }
  function marketMap(m){
    const i=m.current?.marketIntelligence;if(!i)return '';
    const st=i.structure||{},htf=`Monthly ${cap(st.mn1)} · Weekly ${cap(st.w1)} · Daily ${cap(st.d1)} · H4 ${cap(st.h4)}`;
    const liq=i.nearestLiquidity||{},above=levelText(liq.above),below=levelText(liq.below);
    const wr=i.rangeLocation?.currentWeekCompleted,mr=i.rangeLocation?.currentMonthCompleted;
    const ranges=`Week ${cap(wr?.zone||'unknown')}${Number.isFinite(Number(wr?.percentile))?` (${pct(Number(wr.percentile)*100)})`:''} · Month ${cap(mr?.zone||'unknown')}${Number.isFinite(Number(mr?.percentile))?` (${pct(Number(mr.percentile)*100)})`:''}`;
    const cs=i.candles||{},candle=`M15 ${cs.m15?.pattern||'—'} · H1 ${cs.h1?.pattern||'—'} · H4 ${cs.h4?.pattern||'—'}`;
    const p=i.poi||{},parts=[];
    if(p.available){parts.push(p.fvg?.present?'FVG present':'No strict FVG');if(Number.isFinite(Number(p.displacement?.bodyAtr)))parts.push(`${Number(p.displacement.bodyAtr).toFixed(2)} ATR BOS body`);if(p.poiCandle?.pattern)parts.push(p.poiCandle.pattern);if(Number.isFinite(Number(p.penetration?.pct)))parts.push(`${Number(p.penetration.pct).toFixed(0)}% POI penetration`)}
    const poi=parts.length?parts.join(' · '):'POI evidence is not mature yet.';
    return `<div><b>Higher-timeframe structure</b><span>${esc(htf)}. ${esc(i.higherTimeframeContext?.label?`Current setup context is ${i.higherTimeframeContext.label}.`:'Each timeframe is read separately.')}</span></div><div><b>Liquidity map</b><span>Above: ${esc(above)}<br>Below: ${esc(below)}</span></div><div><b>Higher-timeframe location</b><span>${esc(ranges)}. Premium/discount is location context, not a signal.</span></div><div><b>Candle context</b><span>${esc(candle)}. V2 records candle behavior but does not wait for a generic candle confirmation before entering.</span></div><div><b>POI evidence</b><span>${esc(poi)}</span></div>`;
  }
  function details(m){
    const s=m.stats,h=m.hist,v=m.v34,map=marketMap(m);if(!s&&!h&&!map)return '';
    const live=s?`<div><b>Live journal</b><span>${pct(s.decisiveWinRatePct)} decisive win rate · ${pct(s.scoredClosureWinSharePct)} when numeric timeouts are included. ${s.wins} win, ${s.losses} losses, ${s.timeouts} timeout, ${s.ambiguous} ambiguous.</span></div>`:'';
    const hist=h?`<div><b>Why first interaction matters</b><span>In the 2022–2025 historical study, direct first-interaction entries won ${pct(h.directFirstInteraction?.winRatePct)} versus ${pct(h.priorShallowTouch?.winRatePct)} after an earlier shallow touch. This is historical context, not a probability for this trade.</span></div>`:'';
    const research=v?`<div><b>What V3.4 actually proved</b><span>A richer context subset reached ${pct(v.contextScore4SelectedWinRatePct)} decisive wins versus ${pct(v.baselineDecisiveWinRatePct)} baseline, but skipped opportunities made the paired expectancy worse. No higher-timeframe, FVG, candle, Kojo-proxy or Dapo-proxy rule was promoted as a hard trade gate. Generic delayed candle confirmation fell to ${pct(v.candleDelayedEntryWinRatePct)}.</span></div>`:'';
    const cadence=`<div><b>Live cadence</b><span>Paper-plan evaluation, Discord pulse, closure delivery and setup-quality checks now run every minute. The V3.4 higher-timeframe map refreshes every five minutes after pair-state updates. Structural decisions still use completed M15 evidence, so faster scanning does not turn incomplete candles into signals.</span></div>`;
    return `<details class="v31Details"><summary>Why this grade?</summary><div class="v31DetailsBody">${map}${cadence}${research}${live}${hist}<div><b>Boundary</b><span>V2 does not know that a trade will win. Market structure, liquidity, candle and POI reads describe what is happening; the frozen midpoint, stop and target rules remain unchanged.</span></div></div></details>`;
  }
  function cardHTML(m,compact=false){
    const c=m.current,q=c?.quality||{code:'NO_SETUP',label:'No setup to grade',tone:'neutral',reason:'V2 is waiting for a mature setup.',next:'Wait for the normal setup sequence.'};
    const risk=floorText(c),att=attentionText(c),friction=frictionText(c),strip=!compact?mapStrip(c):'';
    return `<div class="v31QualityHead"><div><span>Setup quality</span><strong>${esc(q.label)}</strong></div><span class="v31QualityBadge ${esc(q.tone)}">${esc(m.symbol)}</span></div><p>${esc(q.reason)}</p>${strip}${att?`<p class="v31QualityLive">${esc(att)}</p>`:''}${risk?`<p class="v31QualityNote">${esc(risk)}</p>`:''}${friction?`<p class="v31QualityWarn">${esc(friction)}</p>`:''}${!compact?`<div class="v31Next"><b>What now</b><span>${esc(q.next)}</span></div>${details(m)}`:''}`;
  }
  function renderHome(){const root=$('#focusBoard');if(!root)return;const m=model(),i=m.current?.marketIntelligence,sig=JSON.stringify([m.symbol,m.current?.tradeKey,m.current?.quality?.code,m.current?.risk?.pips,m.current?.fastAttention?.status,m.current?.fastAttention?.distanceToEntryPips,m.stats?.wins,m.stats?.losses,m.stats?.timeouts,i?.version,i?.generatedAt,i?.higherTimeframeContext?.label,i?.nearestLiquidity?.above?.level,i?.nearestLiquidity?.below?.level]);let card=$('#v31SetupQuality',root);if(!card){card=document.createElement('article');card.id='v31SetupQuality';card.className='v31QualityCard';root.querySelector('.focusHero')?.insertAdjacentElement('afterend',card)}if(card&&card.dataset.sig!==sig){card.dataset.sig=sig;card.innerHTML=cardHTML(m)}}
  function renderTrade(){const host=$('#paperCurrent');if(!host)return;const m=model(),c=m.current;if(!c||!c.tradeKey){$('#v31TradeQuality',host)?.remove();return}const sig=JSON.stringify([m.symbol,c.tradeKey,c.quality?.code,c.risk?.pips,c.friction?.status,c.fastAttention?.status,c.fastAttention?.distanceToEntryPips,c.marketIntelligence?.generatedAt]);let card=$('#v31TradeQuality',host);if(!card){card=document.createElement('div');card.id='v31TradeQuality';card.className='v31TradeQuality';host.prepend(card)}if(card.dataset.sig!==sig){card.dataset.sig=sig;card.innerHTML=cardHTML(m,true)}}
  function render(){if(!data)return;renderHome();renderTrade()}
  async function load(force=false){if(loading)return;if(!force&&Date.now()-lastLoad<20000){render();return}loading=true;try{const r=await fetch(URL,{cache:'no-store'});if(r.ok){data=await r.json();window.v31SetupQuality=data;lastLoad=Date.now();render()}}catch{}finally{loading=false}}
  let timer=null;const schedule=()=>{clearTimeout(timer);timer=setTimeout(render,30)};
  const focus=$('#focusBoard');if(focus)new MutationObserver(schedule).observe(focus,{childList:true});
  const paper=$('#paperCurrent');if(paper)new MutationObserver(schedule).observe(paper,{childList:true});
  document.addEventListener('click',e=>{if(e.target.closest?.('[data-pair]'))setTimeout(()=>{render();load(true)},60)});
  document.addEventListener('DOMContentLoaded',()=>load(true));
  load(true);setInterval(()=>{if(!document.hidden)load(true)},60000);
})();
