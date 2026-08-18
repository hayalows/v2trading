(()=>{
'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];

function setupA11y(){
  const main=$('main.wrap');
  if(main&&!main.id)main.id='mainContent';
  if(main&&!$('.skipLink')){
    const link=document.createElement('a');link.className='skipLink';link.href='#mainContent';link.textContent='Skip to content';document.body.prepend(link);
  }
  $('.bottom')?.setAttribute('aria-label','Primary navigation');$('.sideNav')?.setAttribute('aria-label','Primary navigation');
  ['#topStatus','#healthText','#tradeFilterCount'].forEach(s=>$(s)?.setAttribute('aria-live','polite'));
  $$('button:not([type])').forEach(b=>b.type='button');
  function syncNav(id){$$('[data-view]').forEach(b=>{if(b.dataset.view===id)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});document.title=`V2 Trading · ${id.charAt(0).toUpperCase()+id.slice(1)}`}
  syncNav($('.view.active')?.id||'home');window.addEventListener('v2:view',e=>syncNav(e.detail?.id||'home'));
}

function setupHome(){
  const home=$('#home');if(!home||home.dataset.homeUx==='ready')return;
  const head=home.querySelector('.pageHead'),account=home.querySelector('.accountHero'),instrumentSection=home.querySelector('.section'),pairGrid=instrumentSection?.querySelector('.pairGrid');
  if(!head||!account||!instrumentSection||!pairGrid)return;
  home.classList.add('homeV2');account.classList.add('homeAccount');instrumentSection.classList.add('homeInstruments');
  const focus=document.createElement('section');focus.id='homeFocus';focus.className='homeFocus';focus.hidden=true;focus.setAttribute('aria-live','polite');head.insertAdjacentElement('afterend',focus);
  const latest=document.createElement('section');latest.id='homeLatest';latest.className='homeLatest';latest.hidden=true;instrumentSection.insertAdjacentElement('afterend',latest);
  let rendering=false,lastFresh=0,freshTimer=0,latestFast=null;
  const sourceSelectors=['#EURUSDHome','#GBPUSDHome','#EURUSDTrade','#GBPUSDTrade','#tradeList','#record','#balance'];

  function levelMap(sym){const card=$(`#${sym}Trade`),out={};card?.querySelectorAll('.levels>div').forEach(el=>{const key=el.querySelector('span')?.textContent?.trim(),value=el.querySelector('b')?.textContent?.trim();if(key&&value)out[key]=value});return out}
  function cardState(card){const sym=card.id.replace('Home',''),badge=card.querySelector('.stageBadge')?.textContent||'',stage=Number((badge.match(/Stage\s+(\d+)/i)||[])[1]||0),next=card.querySelector('.next span')?.textContent?.trim()||'',stageName=card.querySelector('.stageName')?.textContent?.trim()||'Monitoring',price=card.querySelector('.pairPrice')?.textContent?.trim()||'—',why=card.querySelector('p')?.textContent?.trim()||'',open=/trade is open/i.test(next),armed=/plan is armed/i.test(next),state=open?'open':armed?'armed':stage>=6?'attention':stage>=3?'developing':'watching',priority=open?100+stage:armed?90+stage:stage>=6?70+stage:stage>=3?40+stage:10+stage;return{card,sym,stage,next,stageName,price,why,state,priority}}
  function currentR(sym){const cards=[...document.querySelectorAll(`#tradeList .tradeCard[data-symbol="${sym}"]`)],openCard=cards.find(c=>c.querySelector('.tradeResult')?.textContent?.trim().startsWith('OPEN'));return openCard?.querySelector('.tradeResult small')?.textContent?.trim()||''}
  function fastFor(sym){return latestFast?.symbols?.find?.(x=>x.symbol===sym&&x.activeTradeKey)||null}
  function fastMarkup(top){
    if(!top||!['armed','open'].includes(top.state))return'';
    const f=fastFor(top.sym);if(!f)return'';
    if(f.mode==='BID/ASK fast execution')return `<div class="homeFastExecution ok"><i></i><div><b>Fast execution · BID/ASK ticks</b><span>Frozen entry, stop and target are checked every minute on public BID/ASK ticks.</span></div></div>`;
    if(f.mode==='1m indicative observer')return `<div class="homeFastExecution watch"><i></i><div><b>Fast observer · 1m indicative</b><span>Near-live movement is visible; paper P&amp;L waits for BID/ASK confirmation or the M15 fallback.</span></div></div>`;
    return `<div class="homeFastExecution bad"><i></i><div><b>Fast observer · data delayed</b><span>The frozen plan is preserved while V2 waits for a usable fast execution source.</span></div></div>`;
  }
  function renderFocus(top){
    const needsFocus=top&&(top.state==='open'||top.state==='armed'||top.state==='attention');home.classList.toggle('hasHomeFocus',Boolean(needsFocus));$$('#EURUSDHome,#GBPUSDHome').forEach(c=>{c.hidden=false;c.removeAttribute('data-home-focus')});
    if(!needsFocus){focus.hidden=true;focus.innerHTML='';return}
    top.card.hidden=true;top.card.dataset.homeFocus='true';
    const levels=levelMap(top.sym),rNow=currentR(top.sym),label=top.state==='open'?'Open paper trade':top.state==='armed'?'Plan ready':'Needs attention',status=top.state==='open'?(rNow||'Trade active'):top.state==='armed'?'Waiting for midpoint entry':top.stageName,levelBits=[];
    if(levels.Entry)levelBits.push(`<div><span>Entry</span><b>${levels.Entry}</b></div>`);if(levels.SL)levelBits.push(`<div><span>SL</span><b>${levels.SL}</b></div>`);if(levels.TP)levelBits.push(`<div><span>TP</span><b>${levels.TP}</b></div>`);if(!levelBits.length&&levels.Midpoint)levelBits.push(`<div><span>Midpoint</span><b>${levels.Midpoint}</b></div>`);
    focus.innerHTML=`<div class="homeFocusTop"><div><span class="homeFocusEyebrow">${label}</span><div class="homeFocusTitle"><strong>${top.sym}</strong><span>${top.price}</span></div></div><span class="homeFocusStage">Stage ${top.stage}/8</span></div><div class="homeFocusStatus">${status}</div>${fastMarkup(top)}${levelBits.length?`<div class="homeFocusLevels">${levelBits.join('')}</div>`:''}<div class="homeFocusNext"><span>Next</span><b>${top.next||'Monitor the next completed structural event.'}</b></div>`;focus.hidden=false;
  }
  function renderLatest(){const card=$('#tradeList .tradeCard');if(!card){latest.hidden=true;latest.innerHTML='';return}const sym=card.dataset.symbol||card.querySelector('.tradeTitle strong')?.textContent?.trim()||'Trade',direction=card.querySelector('.direction')?.textContent?.trim()||'',resultEl=card.querySelector('.tradeResult'),main=resultEl?.childNodes?.[0]?.textContent?.trim()||resultEl?.textContent?.trim()||'',sub=resultEl?.querySelector('small')?.textContent?.trim()||'',time=card.querySelector('.tradeWhen')?.textContent?.trim()||'',isOpen=main==='OPEN';latest.innerHTML=`<div class="homeLatestHead"><span>Latest</span><button type="button" class="homeHistoryLink">View history</button></div><button type="button" class="homeLatestRow"><div><strong>${sym}${direction?` · ${direction}`:''}</strong><span>${time}</span></div><div class="homeLatestResult ${resultEl?.classList.contains('bad')?'bad':resultEl?.classList.contains('good')?'good':''}"><b>${isOpen?'Open':main}</b>${sub?`<span>${sub}</span>`:''}</div></button>`;latest.hidden=false;const openHistory=()=>{window.v2SetView?.('trades');setTimeout(()=>document.querySelector('[data-trade-mode="history"]')?.click(),0)};latest.querySelector('.homeHistoryLink')?.addEventListener('click',openHistory);latest.querySelector('.homeLatestRow')?.addEventListener('click',openHistory)}
  function renderHome(){if(rendering)return;rendering=true;try{const states=$$('#EURUSDHome,#GBPUSDHome').map(cardState).sort((a,b)=>b.priority-a.priority);states.forEach(s=>{s.card.dataset.homeState=s.state});states.forEach(s=>pairGrid.appendChild(s.card));renderFocus(states[0]);renderLatest()}finally{rendering=false}}
  function schedule(){requestAnimationFrame(renderHome)}
  const observer=new MutationObserver(schedule);sourceSelectors.forEach(sel=>{const el=$(sel);if(el)observer.observe(el,{childList:true,subtree:true,characterData:true})});
  window.addEventListener('v2:fast-execution',e=>{latestFast=e.detail||null;schedule()});

  const topStatus=$('#topStatus');
  function freshnessText(){if(!lastFresh||!topStatus)return;const current=topStatus.textContent||'';if(/Refreshing|services connected|Connecting/i.test(current))return;const sec=Math.max(0,Math.floor((Date.now()-lastFresh)/1000));topStatus.textContent=sec<10?'Live · just now':sec<60?`Live · ${sec}s ago`:`Live · ${Math.floor(sec/60)}m ago`}
  if(topStatus){const statusObserver=new MutationObserver(()=>{const text=topStatus.textContent||'';if(text==='Live data connected'){lastFresh=Date.now();freshnessText()}});statusObserver.observe(topStatus,{childList:true,characterData:true,subtree:true});freshTimer=setInterval(freshnessText,10000)}
  window.addEventListener('pagehide',()=>{if(freshTimer)clearInterval(freshTimer)},{once:true});renderHome();home.dataset.homeUx='ready';
}

function setupTrades(){
  const view=$('#trades');if(!view||view.dataset.uxTabs==='ready')return;const summary=view.querySelector('.tradeSummary'),sections=[...view.children].filter(el=>el.matches?.('section.section'));if(!summary||sections.length<2)return;const liveSection=sections[0],historySection=sections[1],head=view.querySelector('.pageHead'),tabs=document.createElement('div');tabs.className='tradeSubnav';tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Trades view');tabs.innerHTML='<button type="button" class="tradeSubtab active" role="tab" aria-selected="true" data-trade-mode="live"><span>Live</span><small>Setups & plans</small></button><button type="button" class="tradeSubtab" role="tab" aria-selected="false" data-trade-mode="history"><span>History</span><small>Results & audit</small></button>';head?.insertAdjacentElement('afterend',tabs);summary.dataset.tradePane='live';liveSection.dataset.tradePane='live';historySection.dataset.tradePane='history';historySection.hidden=true;let mode='live';try{mode=sessionStorage.getItem('v2TradeMode')||'live'}catch{}
  function setMode(next,focus=false){mode=next==='history'?'history':'live';$$('[data-trade-pane]').forEach(el=>{el.hidden=el.dataset.tradePane!==mode});tabs.querySelectorAll('[data-trade-mode]').forEach(btn=>{const active=btn.dataset.tradeMode===mode;btn.classList.toggle('active',active);btn.setAttribute('aria-selected',String(active));btn.tabIndex=active?0:-1});try{sessionStorage.setItem('v2TradeMode',mode)}catch{}if(focus)tabs.querySelector(`[data-trade-mode="${mode}"]`)?.focus()}
  tabs.querySelectorAll('[data-trade-mode]').forEach(btn=>btn.addEventListener('click',()=>setMode(btn.dataset.tradeMode)));tabs.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();setMode(mode==='live'?'history':'live',true)});setMode(mode);view.dataset.uxTabs='ready';
}

function setupResearch(){
  const grid=$('#research .researchGrid');if(!grid||grid.dataset.disclosure==='ready')return;const articles=[...grid.querySelectorAll('article')];if(!articles.length)return;grid.classList.add('researchDisclosure');const details=articles.map((article,index)=>{const icon=article.querySelector('.cardIcon'),eyebrow=article.querySelector(':scope > span'),title=article.querySelector('h3'),body=article.querySelector('p'),d=document.createElement('details');d.className='researchItem';const summary=document.createElement('summary');summary.innerHTML='<div class="researchItemLead"></div><span class="researchChevron" aria-hidden="true">⌄</span>';const lead=summary.querySelector('.researchItemLead');if(icon)lead.appendChild(icon);const text=document.createElement('div');text.className='researchItemText';if(eyebrow)text.appendChild(eyebrow);if(title)text.appendChild(title);lead.appendChild(text);const content=document.createElement('div');content.className='researchItemBody';if(body)content.appendChild(body);d.append(summary,content);article.replaceWith(d);if(index===0)d.open=true;return d});const mq=window.matchMedia('(min-width:721px)'),adapt=()=>{if(mq.matches)details.forEach(d=>d.open=true);else if(!details.some(d=>d.open))details[0].open=true};details.forEach(d=>d.addEventListener('toggle',()=>{if(!mq.matches&&d.open)details.forEach(other=>{if(other!==d)other.open=false})}));mq.addEventListener?.('change',adapt);adapt();grid.dataset.disclosure='ready';
}

function setupSegments(){const chart=$('#chart .filters');if(chart){chart.setAttribute('role','tablist');chart.setAttribute('aria-label','Chart instrument');chart.querySelectorAll('[data-chart-pair]').forEach(btn=>{btn.setAttribute('role','tab');btn.setAttribute('aria-selected',String(btn.classList.contains('active')));btn.addEventListener('click',()=>chart.querySelectorAll('[data-chart-pair]').forEach(x=>x.setAttribute('aria-selected',String(x===btn))))})}const pairs=$('.pairSegment');if(pairs){pairs.setAttribute('role','tablist');pairs.setAttribute('aria-label','Trade instrument filter');pairs.querySelectorAll('[data-pair-filter]').forEach(btn=>{btn.setAttribute('role','tab');btn.setAttribute('aria-selected',String(btn.classList.contains('active')));btn.addEventListener('click',()=>pairs.querySelectorAll('[data-pair-filter]').forEach(x=>x.setAttribute('aria-selected',String(x===btn))))})}}

setupA11y();setupHome();setupTrades();setupResearch();setupSegments();
})();
