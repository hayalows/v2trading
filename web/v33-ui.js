(()=>{
  const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
  const set=(el,text)=>{if(el&&el.textContent!==text)el.textContent=text};
  const labels={overview:'Home',chartView:'Chart',tradesView:'Trades',evidenceView:'Research',dataView:'Quality'};

  function baseSemantics(){
    const main=$('.main');
    if(main&&!main.id)main.id='mainContent';
    if(!$('.v33Skip')){
      const a=document.createElement('a');a.className='v33Skip';a.href='#mainContent';a.textContent='Skip to market content';document.body.prepend(a);
    }
    const theme=$('meta[name="theme-color"]');if(theme)theme.content='#090c10';
    const market=$('#marketText');if(market){market.parentElement?.setAttribute('role','status');market.parentElement?.setAttribute('aria-live','polite')}
    const refresh=$('#refresh');if(refresh){refresh.type='button';refresh.title='Refresh market data';refresh.setAttribute('aria-label','Refresh market data')}
    $$('button:not([type])').forEach(b=>b.type='button');
  }

  function copy(){
    set($('.brand b'),'V2');
    set($('.brand span'),'Research · paper only');
    set($('.intro .eyebrow'),'EURUSD + GBPUSD');
    set($('.intro h1'),'What matters right now');
    set($('.intro p'),'See the current stage, the next condition, and the active paper state. Research only, with no live execution.');

    $$('[data-view]').forEach(btn=>{
      const label=labels[btn.dataset.view];if(!label)return;
      const text=$('span:last-child',btn);if(text)set(text,label);
      if(btn.matches('.navBtn,.railBtn'))btn.setAttribute('aria-label',label);
    });

    set($('#chartView .sectionHead h2'),'Chart');
    set($('#chartView .sectionHead p'),'Check the market structure visually. The chart does not place or recommend live orders.');
    set($('#tradesView .sectionHead h2'),'Trades');
    set($('#tradesView .sectionHead p'),'Automatic paper plans, entries and outcomes. No live orders are sent.');
    set($('#evidenceView .sectionHead h2'),'Research');
    set($('#evidenceView .sectionHead p'),'Historical studies and model evidence, kept separate from the live market view.');
    set($('#dataView .sectionHead h2'),'Data quality');
    set($('#dataView .sectionHead p'),'Sources, freshness, coverage and the limits of what V2 can know.');

    const summary=$('.researchDisclosure>summary span:first-child');
    if(summary&&!summary.dataset.v33){summary.innerHTML='More research context<small>Trends, diagnostics and model evidence</small>';summary.dataset.v33='1'}
  }

  function syncSelection(){
    const activeView=$('.view.active')?.id||'overview';
    $$('[data-view]').forEach(btn=>{
      const on=btn.dataset.view===activeView;
      if(on)btn.setAttribute('aria-current','page');else btn.removeAttribute('aria-current');
    });
    $$('.pairBtn').forEach(btn=>btn.setAttribute('aria-pressed',btn.classList.contains('active')?'true':'false'));
    const label=labels[activeView]||'V2';document.title=`${label} · V2`;
  }

  function qualityDisclosure(){
    const card=$('#v31SetupQuality');if(!card)return;
    if(!card.id)card.id='v31SetupQuality';
    let toggle=$('.v33QualityToggle',card);
    if(!toggle){
      toggle=document.createElement('button');toggle.type='button';toggle.className='v33QualityToggle';toggle.setAttribute('aria-controls','v31SetupQuality');toggle.setAttribute('aria-expanded','false');toggle.textContent='Why this rating';
      toggle.addEventListener('click',()=>{
        const open=card.classList.toggle('v33QualityExpanded');toggle.setAttribute('aria-expanded',String(open));set(toggle,open?'Hide explanation':'Why this rating');
      });
      card.appendChild(toggle);
    }
  }

  function stageButtonCopy(){
    const button=$('.v32StageButton');if(!button)return;
    const small=$('small',button),strong=$('strong',button);if(small)set(small,'How the setup progresses');if(strong&&/stage/i.test(strong.textContent||''))set(strong,strong.textContent.replace(/stage/ig,'step'));
  }

  let busy=false;
  function enhance(){
    if(busy)return;busy=true;
    requestAnimationFrame(()=>{busy=false;baseSemantics();copy();syncSelection();qualityDisclosure();stageButtonCopy();window.v32UpgradeIcons?.()});
  }
  new MutationObserver(enhance).observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});
  document.addEventListener('click',e=>{if(e.target.closest?.('[data-view],[data-pair]'))setTimeout(enhance,0)});
  document.addEventListener('DOMContentLoaded',enhance);
  enhance();
})();
