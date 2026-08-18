(()=>{
'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];

function setupA11y(){
  const main=$('main.wrap');
  if(main&&!main.id)main.id='mainContent';
  if(main&&!$('.skipLink')){
    const link=document.createElement('a');
    link.className='skipLink';
    link.href='#mainContent';
    link.textContent='Skip to content';
    document.body.prepend(link);
  }
  $('.bottom')?.setAttribute('aria-label','Primary navigation');
  $('.sideNav')?.setAttribute('aria-label','Primary navigation');
  ['#topStatus','#healthText','#tradeFilterCount'].forEach(s=>$(s)?.setAttribute('aria-live','polite'));
  $$('button:not([type])').forEach(b=>b.type='button');
  function syncNav(id){
    $$('[data-view]').forEach(b=>{
      if(b.dataset.view===id)b.setAttribute('aria-current','page');
      else b.removeAttribute('aria-current');
    });
    document.title=`V2 Trading · ${id.charAt(0).toUpperCase()+id.slice(1)}`;
  }
  syncNav($('.view.active')?.id||'home');
  window.addEventListener('v2:view',e=>syncNav(e.detail?.id||'home'));
}

function setupTrades(){
  const view=$('#trades');
  if(!view||view.dataset.uxTabs==='ready')return;
  const summary=view.querySelector('.tradeSummary');
  const sections=[...view.children].filter(el=>el.matches?.('section.section'));
  if(!summary||sections.length<2)return;
  const liveSection=sections[0],historySection=sections[1];
  const head=view.querySelector('.pageHead');
  const tabs=document.createElement('div');
  tabs.className='tradeSubnav';
  tabs.setAttribute('role','tablist');
  tabs.setAttribute('aria-label','Trades view');
  tabs.innerHTML='<button type="button" class="tradeSubtab active" role="tab" aria-selected="true" data-trade-mode="live"><span>Live</span><small>Setups & plans</small></button><button type="button" class="tradeSubtab" role="tab" aria-selected="false" data-trade-mode="history"><span>History</span><small>Results & audit</small></button>';
  head?.insertAdjacentElement('afterend',tabs);
  summary.dataset.tradePane='live';
  liveSection.dataset.tradePane='live';
  historySection.dataset.tradePane='history';
  historySection.hidden=true;
  let mode='live';
  try{mode=sessionStorage.getItem('v2TradeMode')||'live'}catch{}
  function setMode(next,focus=false){
    mode=next==='history'?'history':'live';
    $$('[data-trade-pane]').forEach(el=>{el.hidden=el.dataset.tradePane!==mode});
    tabs.querySelectorAll('[data-trade-mode]').forEach(btn=>{
      const active=btn.dataset.tradeMode===mode;
      btn.classList.toggle('active',active);
      btn.setAttribute('aria-selected',String(active));
      btn.tabIndex=active?0:-1;
    });
    try{sessionStorage.setItem('v2TradeMode',mode)}catch{}
    if(focus)tabs.querySelector(`[data-trade-mode="${mode}"]`)?.focus();
  }
  tabs.querySelectorAll('[data-trade-mode]').forEach(btn=>btn.addEventListener('click',()=>setMode(btn.dataset.tradeMode)));
  tabs.addEventListener('keydown',e=>{
    if(!['ArrowLeft','ArrowRight'].includes(e.key))return;
    e.preventDefault();
    setMode(mode==='live'?'history':'live',true);
  });
  setMode(mode);
  view.dataset.uxTabs='ready';
}

function setupResearch(){
  const grid=$('#research .researchGrid');
  if(!grid||grid.dataset.disclosure==='ready')return;
  const articles=[...grid.querySelectorAll('article')];
  if(!articles.length)return;
  grid.classList.add('researchDisclosure');
  const details=articles.map((article,index)=>{
    const icon=article.querySelector('.cardIcon');
    const eyebrow=article.querySelector(':scope > span');
    const title=article.querySelector('h3');
    const body=article.querySelector('p');
    const d=document.createElement('details');
    d.className='researchItem';
    const summary=document.createElement('summary');
    summary.innerHTML='<div class="researchItemLead"></div><span class="researchChevron" aria-hidden="true">⌄</span>';
    const lead=summary.querySelector('.researchItemLead');
    if(icon)lead.appendChild(icon);
    const text=document.createElement('div');
    text.className='researchItemText';
    if(eyebrow)text.appendChild(eyebrow);
    if(title)text.appendChild(title);
    lead.appendChild(text);
    const content=document.createElement('div');
    content.className='researchItemBody';
    if(body)content.appendChild(body);
    d.append(summary,content);
    article.replaceWith(d);
    if(index===0)d.open=true;
    return d;
  });
  const mq=window.matchMedia('(min-width:721px)');
  const adapt=()=>{
    if(mq.matches)details.forEach(d=>d.open=true);
    else if(!details.some(d=>d.open))details[0].open=true;
  };
  details.forEach(d=>d.addEventListener('toggle',()=>{
    if(!mq.matches&&d.open)details.forEach(other=>{if(other!==d)other.open=false});
  }));
  mq.addEventListener?.('change',adapt);
  adapt();
  grid.dataset.disclosure='ready';
}

function setupSegments(){
  const chart=$('#chart .filters');
  if(chart){
    chart.setAttribute('role','tablist');
    chart.setAttribute('aria-label','Chart instrument');
    chart.querySelectorAll('[data-chart-pair]').forEach(btn=>{
      btn.setAttribute('role','tab');
      btn.setAttribute('aria-selected',String(btn.classList.contains('active')));
      btn.addEventListener('click',()=>chart.querySelectorAll('[data-chart-pair]').forEach(x=>x.setAttribute('aria-selected',String(x===btn))));
    });
  }
  const pairs=$('.pairSegment');
  if(pairs){
    pairs.setAttribute('role','tablist');
    pairs.setAttribute('aria-label','Trade instrument filter');
    pairs.querySelectorAll('[data-pair-filter]').forEach(btn=>{
      btn.setAttribute('role','tab');
      btn.setAttribute('aria-selected',String(btn.classList.contains('active')));
      btn.addEventListener('click',()=>pairs.querySelectorAll('[data-pair-filter]').forEach(x=>x.setAttribute('aria-selected',String(x===btn))));
    });
  }
}

setupA11y();
setupTrades();
setupResearch();
setupSegments();
})();
