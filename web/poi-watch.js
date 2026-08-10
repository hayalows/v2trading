(()=>{
  const STYLE_ID='v2-poi-watch-style';
  if(!document.getElementById(STYLE_ID)){
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      .poiWatch{border:1px solid var(--line);background:linear-gradient(145deg,var(--surface2),var(--surface));border-radius:var(--r2);padding:17px;overflow:hidden}
      .poiWatchHead{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
      .poiWatchLabel{display:flex;align-items:center;gap:8px;color:var(--primary);font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
      .poiBadge{border-radius:var(--pill);padding:6px 9px;background:var(--surface3);font-size:10px;font-weight:800;color:var(--muted);white-space:nowrap}
      .poiBadge.ready{background:var(--successC);color:var(--success)}
      .poiBadge.near{background:var(--warningC);color:var(--warning)}
      .poiWatch h3{font-size:20px;line-height:1.2;margin:9px 0 7px;letter-spacing:-.02em}
      .poiWatch p{font-size:13px;line-height:1.5;color:var(--muted);margin:0}
      .poiZone{margin-top:14px;border:1px solid var(--line);border-radius:16px;background:var(--surface3);overflow:hidden}
      .poiZoneTitle{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;border-bottom:1px solid var(--line);font-size:11px;color:var(--muted)}
      .poiPrices{display:grid;grid-template-columns:1fr 1fr}
      .poiPrice{padding:13px 12px}
      .poiPrice+ .poiPrice{border-left:1px solid var(--line)}
      .poiPrice span{display:block;color:var(--muted);font-size:10px}
      .poiPrice b{display:block;font-size:19px;margin-top:4px;letter-spacing:-.02em}
      .poiMeta{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
      .poiMetaItem{background:var(--surface3);border-radius:12px;padding:10px}
      .poiMetaItem span{display:block;color:var(--muted);font-size:10px}
      .poiMetaItem b{display:block;font-size:12px;margin-top:4px}
      .poiNext{margin-top:12px;padding:12px;border-radius:14px;background:var(--secondaryC)}
      .poiNext span{display:block;color:#dce5f8;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.05em}
      .poiNext b{display:block;font-size:13px;line-height:1.45;margin-top:5px;color:#eef4ff}
      .poiActions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
      .poiActions button{border:0;border-radius:var(--pill);padding:0 15px;display:inline-flex;align-items:center;justify-content:center;gap:7px;font-size:12px;font-weight:800;cursor:pointer}
      .poiPrimary{background:var(--primary);color:var(--onPrimary)}
      .poiSecondary{background:var(--surface3);color:var(--text)}
      .poiPending{margin-top:14px;padding:14px;border:1px dashed var(--line);border-radius:16px;background:rgba(32,39,49,.45)}
      .poiPending b{display:block;font-size:14px}
      .poiPending span{display:block;color:var(--muted);font-size:12px;line-height:1.45;margin-top:5px}
      @media(max-width:520px){.poiPrices{grid-template-columns:1fr}.poiPrice+ .poiPrice{border-left:0;border-top:1px solid var(--line)}.poiMeta{grid-template-columns:1fr}.poiWatch{padding:15px}}
    `;
    document.head.appendChild(style);
  }

  const asNum=v=>(v===null||v===undefined||v==='')?Number.NaN:Number(v);
  const finite=v=>Number.isFinite(asNum(v));
  const fmtPrice=v=>finite(v)?asNum(v).toFixed(5):'—';
  const fmtAtr=v=>finite(v)?`${asNum(v).toFixed(2)} ATR`:'—';

  function ensurePoiSlot(){
    let slot=document.getElementById('poiWatchSlot');
    if(slot)return slot;
    const stack=document.querySelector('#overview .stack');
    if(!stack)return null;
    slot=document.createElement('div');
    slot.id='poiWatchSlot';
    const campaignSlot=document.getElementById('episodeSlot');
    if(campaignSlot&&campaignSlot.parentNode===stack) stack.insertBefore(slot,campaignSlot);
    else stack.prepend(slot);
    return slot;
  }

  function poiState(s){
    const stage=Number(s?.formation_stage||0),direction=s?.formation_direction||null;
    const low=asNum(s?.poi_low),high=asNum(s?.poi_high);
    const structure=asNum(s?.details?.structure_reference_price);
    const distance=asNum(s?.distance_to_poi_atr);
    const hasZone=stage>=6&&Number.isFinite(low)&&Number.isFinite(high)&&high>=low;

    if(!hasZone){
      if(stage<=2)return{status:'Not active',headline:'No POI to watch yet',body:'A POI only becomes relevant after a valid liquidity sequence develops and structure confirms.',next:'Wait for a clean Stage-3 sweep before looking for a POI.'};
      if(stage===3)return{status:'Pending',headline:'Sweep confirmed · POI not defined yet',body:'The liquidity event is visible, but a fresh POI cannot be trusted before BOS.',next:'Wait for break of structure. Do not invent a POI before confirmation.'};
      if(stage===4)return{status:'Waiting for BOS',headline:'POI not available yet',body:'The campaign is waiting for break of structure. The lab will only publish a fresh POI after that structural confirmation.',next:`Wait for ${direction||'the'} BOS. If it confirms, the lab will identify the fresh origin zone.`};
      if(stage===5)return{status:'Locating POI',headline:'BOS confirmed · fresh POI is being identified',body:'Structure has confirmed, but the fresh origin zone has not yet passed the POI rules.',next:'Wait for the fresh POI to be identified before watching for a return.'};
      return{status:'Unavailable',headline:'POI data is not available',body:'The formation is mature, but the current state does not contain a valid POI range.',next:'Treat this as a data/research discrepancy and verify the chart before interpreting the setup.'};
    }

    const inside=Number.isFinite(structure)&&structure>=low&&structure<=high;
    const near=Number.isFinite(distance)&&distance<=0.35;
    const status=inside||stage>=8?'POI reached':near||stage>=7?'Approaching POI':'Fresh POI found';
    let relation='Structure price unavailable';
    if(Number.isFinite(structure)) relation=inside?'Price is inside the POI zone':structure>high?'Price is above the POI zone':'Price is below the POI zone';

    let next='Watch how price behaves if it returns to the POI. This is a research location, not an execution instruction.';
    if(direction==='long'&&Number.isFinite(structure)&&structure>high) next=`Watch for price to retrace down toward ${fmtPrice(high)}–${fmtPrice(low)}.`;
    if(direction==='short'&&Number.isFinite(structure)&&structure<low) next=`Watch for price to retrace up toward ${fmtPrice(low)}–${fmtPrice(high)}.`;
    if(inside) next='Price is inside the POI zone. Inspect the chart and record the interaction; do not treat zone entry as an automatic trade.';

    return{status,headline:`${direction?direction[0].toUpperCase()+direction.slice(1)+' ':''}fresh POI`,body:'The lab has confirmed BOS and identified the fresh origin zone. This is the exact area to watch for a possible return.',next,low,high,structure,distance,relation,hasZone:true,near,inside};
  }

  function renderPoiWatch(){
    const slot=ensurePoiSlot();
    if(!slot||typeof state!=='function')return;
    const s=state(),p=poiState(s),stage=Number(s?.formation_stage||0);
    const badgeClass=p.hasZone?(p.inside||p.near?'near':'ready'):'';
    let body=`<article class="poiWatch" aria-label="POI watch">
      <div class="poiWatchHead"><div class="poiWatchLabel"><span class="material-symbols-rounded">my_location</span>POI Watch</div><span class="poiBadge ${badgeClass}">${p.status}</span></div>
      <h3>${esc(p.headline)}</h3><p>${esc(p.body)}</p>`;
    if(p.hasZone){
      body+=`<div class="poiZone"><div class="poiZoneTitle"><span>Fresh POI zone</span><span>Stage ${stage}/8</span></div><div class="poiPrices"><div class="poiPrice"><span>POI high</span><b>${fmtPrice(p.high)}</b></div><div class="poiPrice"><span>POI low</span><b>${fmtPrice(p.low)}</b></div></div></div>
        <div class="poiMeta"><div class="poiMetaItem"><span>Structure price</span><b>${fmtPrice(p.structure)}</b></div><div class="poiMetaItem"><span>Distance to POI</span><b>${fmtAtr(p.distance)}</b></div><div class="poiMetaItem"><span>Location</span><b>${esc(p.relation)}</b></div><div class="poiMetaItem"><span>Direction</span><b>${esc(cap(s?.formation_direction||'—'))}</b></div></div>`;
    }else{
      body+=`<div class="poiPending"><b>Stage ${stage}/8 · ${esc(s?.formation_label||s?.formation_code||'No active formation')}</b><span>${esc(p.next)}</span></div>`;
    }
    body+=`<div class="poiNext"><span>What to look for next</span><b>${esc(p.next)}</b></div><div class="poiActions"><button class="poiPrimary" data-poi-chart><span class="material-symbols-rounded">candlestick_chart</span>${p.hasZone?'Inspect on chart':'Open chart'}</button>${p.hasZone?'<button class="poiSecondary" data-poi-copy><span class="material-symbols-rounded">content_copy</span>Copy POI zone</button>':''}</div></article>`;
    slot.innerHTML=body;
    slot.querySelector('[data-poi-chart]')?.addEventListener('click',()=>setView('chartView'));
    slot.querySelector('[data-poi-copy]')?.addEventListener('click',async()=>{
      const text=`${selected} ${cap(s?.formation_direction||'')} POI: ${fmtPrice(p.low)} - ${fmtPrice(p.high)}`;
      try{await navigator.clipboard.writeText(text); if(typeof snack==='function')snack('POI zone copied');}catch{if(typeof snack==='function')snack('Could not copy POI zone');}
    });
    const chartState=document.getElementById('chartState');
    if(chartState&&p.hasZone)chartState.textContent=`${chartState.textContent.split(' · POI')[0]} · POI ${fmtPrice(p.low)}–${fmtPrice(p.high)}`;
    else if(chartState)chartState.textContent=`${chartState.textContent.split(' · POI')[0]} · POI pending`;
  }

  if(typeof render==='function'){
    const baseRender=render;
    render=function(){baseRender();renderPoiWatch();};
  }
  renderPoiWatch();
})();