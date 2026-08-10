(()=>{
  const PAPER='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/paper-trade-engine?symbol=EURUSD,GBPUSD&bars=1';
  let paperData={summary:{},trades:[],events:[],chartBars:{}},paperChart=null,paperSeries=null,paperMarkers=null,paperBusy=false;
  const pnum=(v,d=5)=>(v===null||v===undefined||v===''||!Number.isFinite(Number(v)))?'—':Number(v).toFixed(d);
  const ptime=t=>t?new Date(t).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'—';
  const statuses={armed:'Waiting for POI',open:'Paper trade open',win:'Target reached',loss:'Stop reached',timeout:'Timed out',ambiguous:'Ambiguous path',expired:'Legacy expiry',invalid:'Plan rejected'};
  const phases={fresh_wait:'Fresh wait',extended_wait:'Extended wait',long_tail_wait:'Long-tail wait',outside_studied_tail:'Outside studied tail',filled:'Filled',closed:'Closed'};
  const conditions={intact:'POI intact',partially_mitigated:'POI partially mitigated',target_delivered_before_entry:'Move extended before entry',partially_mitigated_after_target:'Mitigated after large extension'};
  function tradesFor(s=selected){return (paperData.trades||[]).filter(t=>t.symbol===s)}
  function focusTrade(s=selected){const xs=tradesFor(s);return xs.find(t=>t.status==='open')||xs.find(t=>t.status==='armed')||xs[0]||null}
  function badge(t){return `<span class="paperBadge ${esc(t?.status||'')}">${esc(statuses[t?.status]||cap(t?.status||'No plan'))}</span>`}
  function level(label,value,cls=''){return `<div class="paperLevel ${cls}"><span>${esc(label)}</span><b>${esc(value)}</b></div>`}
  function lifecycleLabel(t){return phases[t?.lifecycle_phase]||cap(t?.lifecycle_phase||'fresh wait')}
  function conditionLabel(t){return conditions[t?.setup_condition]||cap(t?.setup_condition||'intact')}
  function waitHours(t){return Number.isFinite(Number(t?.pending_age_bars))?(Number(t.pending_age_bars)*.25).toFixed(Number(t.pending_age_bars)%4?2:0):'—'}
  function paperCopy(t){
    if(!t)return 'No automatic paper trade has been armed for this pair yet.';
    if(t.status==='armed'){
      const age=Number(t.pending_age_bars||0),phase=t.lifecycle_phase||'fresh_wait';
      if(phase==='outside_studied_tail')return 'The midpoint still has not filled. The lab continues tracking it, but its age is now beyond the 48-hour waiting-time tail studied in v1.4, so no historical waiting claim is attached to it.';
      if(t.setup_condition==='partially_mitigated'||t.setup_condition==='partially_mitigated_after_target')return 'Price has interacted with the POI without reaching the midpoint. Historical proxy results were materially weaker after this kind of shallow mitigation, so the plan stays observable but is clearly downgraded rather than silently cancelled.';
      if(t.pre_entry_target_reached)return `The POI remains unfilled after ${age} completed M15 bars. Price already delivered at least 2.5R of favorable extension before entry; v1.4 records this as context, not an automatic invalidation.`;
      if(age>8)return `The old eight-bar window has passed, but v1.4 research showed that many valid midpoint revisits occurred later. The POI remains intact and the lab is still waiting rather than expiring it on time alone.`;
      return 'The lab has a valid plan and is waiting for a future completed M15 bar to revisit the POI midpoint. Nothing has been counted as an entry yet.';
    }
    if(t.status==='open')return 'The POI midpoint was revisited and the research paper trade is now open. The engine is tracking stop, 2.5R target, MFE and MAE automatically.';
    if(t.status==='win')return 'The public completed-candle research path reached the 2.5R target after entry.';
    if(t.status==='loss')return 'The public completed-candle research path reached the planned stop after entry.';
    if(t.status==='timeout')return 'Neither stop nor 2.5R target resolved within the frozen 48-bar post-entry holding window; the trade was marked to market.';
    if(t.status==='ambiguous')return `The public bars could not establish a defensible ordering. ${t.ambiguous_reason||'The result remains unresolved.'}`;
    if(t.status==='expired')return 'This is a legacy v1.3 expiry record. v1.4 removes time-only cancellation and re-evaluates eligible legacy plans.';
    return t?.context?.invalid_reason?`The candidate was recorded but rejected by the frozen risk gate: ${t.context.invalid_reason}.`:'This candidate did not satisfy the frozen paper-trade rules.';
  }
  function lifecycleNotice(t){
    if(!t||t.status!=='armed')return '';
    const age=Number(t.pending_age_bars||0),pre=Number(t.pre_entry_max_favorable_r);
    return `<div class="paperNotice"><strong>${esc(lifecycleLabel(t))} · ${esc(conditionLabel(t))}</strong>${age} completed M15 bars since BOS (${waitHours(t)}h of trading bars). ${age>8?'The former eight-bar cutoff has passed; this is not treated as invalidation. ':''}${Number.isFinite(pre)?`Maximum favorable extension before entry: ${pnum(pre,2)}R. `:''}${t.first_zone_touch_at?`First shallow POI interaction: ${ptime(t.first_zone_touch_at)}. `:'POI midpoint has not been reached.'}</div>`;
  }
  function paperCard(t,compact=false){
    if(!t)return `<article class="card"><div class="cardLabel"><span class="material-symbols-rounded">smart_toy</span>Automatic paper trade</div><h3>No paper plan armed</h3><p>The lab will create one automatically only after BOS confirms and a fresh POI passes the frozen risk rules.</p></article>`;
    const gross=t.gross_r==null?'—':`${Number(t.gross_r)>=0?'+':''}${pnum(t.gross_r,2)}R`;
    const title=`${t.symbol} ${cap(t.direction)} · ${statuses[t.status]||cap(t.status)}`;
    return `<article class="${compact?'card':'paperCurrent'}"><div class="paperTop"><div><div class="cardLabel"><span class="material-symbols-rounded">smart_toy</span>Automatic paper trade</div><h3>${esc(title)}</h3></div>${badge(t)}</div><p>${esc(paperCopy(t))}</p><div class="paperLevels">${level('POI',`${pnum(t.poi_low)} – ${pnum(t.poi_high)}`)}${level('Entry midpoint',pnum(t.entry_price),'entry')}${level('Stop loss',pnum(t.stop_price),'stop')}${level('Take profit · 2.5R',pnum(t.target_price),'target')}</div><div class="paperMeta"><span class="chip">${esc(lifecycleLabel(t))}</span><span class="chip">${esc(conditionLabel(t))}</span><span class="chip">Age ${t.pending_age_bars??'—'} bars</span><span class="chip">Risk ${pnum(t.risk_atr,2)} ATR</span><span class="chip">MFE ${t.mfe_r==null?'—':pnum(t.mfe_r,2)+'R'}</span><span class="chip">MAE ${t.mae_r==null?'—':pnum(t.mae_r,2)+'R'}</span><span class="chip">Result ${gross}</span></div>${lifecycleNotice(t)}<div class="paperNotice"><strong>Research simulation</strong>Entry, SL and TP are evaluated from public completed candles. They are not broker fills and do not include live spread or slippage.</div></article>`;
  }
  function renderPaperOverview(){const slot=document.getElementById('paperTradeSlot');if(slot)slot.innerHTML=paperCard(focusTrade(),true)}
  function stat(label,v){return `<div class="tradeStat"><b>${v}</b><span>${esc(label)}</span></div>`}
  function tradeRow(t){return `<article class="tradeRow"><div class="tradeRowHead"><div><b>${esc(t.symbol)} ${esc(cap(t.direction))}</b><small>Armed ${ptime(t.armed_at)} · ${esc(t.context?.market_session||'session unknown')}</small></div>${badge(t)}</div><div class="paperMeta"><span class="chip">${esc(lifecycleLabel(t))}</span><span class="chip">${esc(conditionLabel(t))}</span>${t.status==='armed'?`<span class="chip">${t.pending_age_bars??0} bars waiting</span>`:''}</div><div class="tradeMini"><div><span>Entry</span><b>${pnum(t.entry_price)}</b></div><div><span>SL</span><b>${pnum(t.stop_price)}</b></div><div><span>TP</span><b>${pnum(t.target_price)}</b></div><div><span>Entered</span><b>${ptime(t.entry_at)}</b></div><div><span>Exited</span><b>${ptime(t.exit_at)}</b></div><div><span>Gross result</span><b>${t.gross_r==null?'—':`${Number(t.gross_r)>=0?'+':''}${pnum(t.gross_r,2)}R`}</b></div></div></article>`}
  function renderTradesView(){
    const all=paperData.trades||[],sum=Object.values(paperData.summary||{}).reduce((a,s)=>({total:a.total+(s.total||0),armed:a.armed+(s.armed||0),open:a.open+(s.open||0),wins:a.wins+(s.wins||0),losses:a.losses+(s.losses||0)}),{total:0,armed:0,open:0,wins:0,losses:0});
    const stats=document.getElementById('paperStats');if(stats)stats.innerHTML=stat('plans recorded',sum.total)+stat('waiting for midpoint',sum.armed)+stat('open paper trades',sum.open)+stat('wins recorded',sum.wins)+stat('losses recorded',sum.losses);
    const current=document.getElementById('paperCurrent');if(current)current.innerHTML=paperCard(focusTrade()).replace(/^<article class="paperCurrent">|<\/article>$/g,'');
    const list=document.getElementById('paperHistory');if(list)list.innerHTML=all.length?all.map(tradeRow).join(''):'<div class="paperEmpty">No paper-trade plans have been recorded yet. The engine waits for a fresh Stage-6+ POI and then arms the midpoint plan automatically.</div>';
    const label=document.getElementById('researchChartLabel');if(label){const t=focusTrade();label.textContent=t?`${selected} · ${statuses[t.status]||cap(t.status)} · ${lifecycleLabel(t)} · entry ${pnum(t.entry_price)}`:`${selected} · no paper plan yet`}
    if(typeof view!=='undefined'&&view==='tradesView')renderResearchChart();
  }
  function clearPaperChart(){if(paperChart){try{paperChart.remove()}catch{}paperChart=null;paperSeries=null;paperMarkers=null}}
  function markerTime(ts,bars){const step=900;const sec=Math.floor(new Date(ts).getTime()/1000/step)*step;return bars.some(b=>Math.floor(new Date(b.ts).getTime()/1000)===sec)?sec:null}
  function renderResearchChart(){
    const el=document.getElementById('researchChart');if(!el)return;const bars=(paperData.chartBars?.[selected]||[]);clearPaperChart();
    if(!bars.length||!window.LightweightCharts){el.innerHTML='<div class="paperEmpty">Research chart data is not available yet.</div>';return}
    el.innerHTML='';paperChart=LightweightCharts.createChart(el,{autoSize:true,layout:{background:{type:'solid',color:'#070a0e'},textColor:'#bfc6d0',attributionLogo:true},grid:{vertLines:{color:'#171d25'},horzLines:{color:'#171d25'}},rightPriceScale:{borderColor:'#3e4651'},timeScale:{borderColor:'#3e4651',timeVisible:true,secondsVisible:false},crosshair:{mode:0}});
    paperSeries=paperChart.addSeries(LightweightCharts.CandlestickSeries,{upColor:'#8fd8aa',downColor:'#ffb4ab',borderVisible:false,wickUpColor:'#8fd8aa',wickDownColor:'#ffb4ab',priceLineVisible:false});
    const data=bars.map(b=>({time:Math.floor(new Date(b.ts).getTime()/1000),open:Number(b.open),high:Number(b.high),low:Number(b.low),close:Number(b.close)}));paperSeries.setData(data);
    const t=focusTrade();if(t){
      const lines=[[Number(t.poi_low),'POI low','#f3c46f',2],[Number(t.poi_high),'POI high','#f3c46f',2],[Number(t.entry_price),'Entry','#a8c7fa',0],[Number(t.stop_price),'SL','#ffb4ab',2],[Number(t.target_price),'TP 2.5R','#8fd8aa',2]];for(const [price,title,color,style] of lines)if(Number.isFinite(price))paperSeries.createPriceLine({price,title,color,lineWidth:2,lineStyle:style,axisLabelVisible:true,lineVisible:true});
      const ev=(paperData.events||[]).filter(e=>e.trade_key===t.trade_key).slice().reverse(),markers=[];for(const e of ev){const mt=markerTime(e.event_at,bars);if(mt==null)continue;let text=cap(e.event_type),shape='circle',position='aboveBar',color='#a8c7fa';if(e.event_type==='entry'){shape=t.direction==='long'?'arrowUp':'arrowDown';position=t.direction==='long'?'belowBar':'aboveBar';color='#a8c7fa'}if(e.event_type==='win'){color='#8fd8aa';text='TP'}if(e.event_type==='loss'){color='#ffb4ab';text='SL'}if(e.event_type==='partially_mitigated'){color='#f3c46f';text='POI touch'}if(e.event_type==='reactivated_v14'){color='#c4b5fd';text='v1.4 reactivated'}markers.push({time:mt,position,shape,color,text})}if(markers.length)paperMarkers=LightweightCharts.createSeriesMarkers(paperSeries,markers);
    }
    paperChart.timeScale().fitContent();
  }
  async function refreshPaper(manual=false){if(paperBusy)return;paperBusy=true;try{const r=await fetch(PAPER,{cache:'no-store'});if(!r.ok)throw new Error('paper trade engine');paperData=await r.json();renderPaperOverview();renderTradesView();if(manual&&typeof snack==='function')snack('Paper-trade lifecycle refreshed')}catch(e){if(manual&&typeof snack==='function')snack('Paper-trade data unavailable')}finally{paperBusy=false}}
  if(typeof render==='function'){const baseRender=render;render=function(){baseRender();renderPaperOverview();renderTradesView()}}
  if(typeof setView==='function'){const baseSetView=setView;setView=function(id){baseSetView(id);if(id==='tradesView')setTimeout(renderResearchChart,0)}}
  document.getElementById('refresh')?.addEventListener('click',()=>refreshPaper(true));
  refreshPaper();setInterval(()=>refreshPaper(false),60_000);
})();