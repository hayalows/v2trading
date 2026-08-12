(()=>{
  const mq=window.matchMedia('(max-width:719px)');
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  function mobile(){return mq.matches}
  function copy(selector,text){const el=$(selector);if(el)el.textContent=text}
  function staticCopy(){
    if(!mobile())return;
    document.documentElement.classList.add('v28Mobile');
    copy('.brand b','V2 Market Lab');copy('.brand span','Paper trading research');
    copy('.intro .eyebrow','EURUSD · GBPUSD');copy('.intro h1','What matters right now');copy('.intro p','See the current setup, what to wait for next, and the key paper-trade levels.');
    const rs=$('.researchDisclosure>summary span:first-child');if(rs)rs.innerHTML='More market details<small>Trends, data and research</small>';
    copy('#chartView .sectionHead p','Use the chart to check the setup visually. It does not place trades.');
    copy('#tradesView .sectionHead p','See paper-trade plans, entries, stops, targets and recorded outcomes.');
    copy('#evidenceView .sectionHead p','See the research behind V2. These results describe past data; they are not trade signals.');
    copy('#dataView .sectionHead p','See how fresh the data is and where V2 has limits.');
    const chartCard=$('#chartView .card');if(chartCard){const h=$('h3',chartCard),p=$('p',chartCard);if(h)h.textContent='Open Trades to see V2 levels on the chart.';if(p)p.textContent='The trade chart shows the entry zone (POI), entry, stop loss and target used by the paper engine.'}
    const frozen=$('#tradesView .paperWorkspace .card');if(frozen){const label=$('.cardLabel',frozen),h=$('h3',frozen),p=$('p',frozen),note=$('.paperNotice',frozen);if(label)label.innerHTML='<span class="material-symbols-rounded">rule</span>Paper-trade rules';if(h)h.textContent='Entry zone midpoint → stop → 2.5R target';if(p)p.textContent='Entry is the middle of the entry zone (POI). The stop stays beyond the liquidity sweep. The target stays at 2.5 times the amount at risk.';if(note)note.innerHTML='<strong>Research only</strong>Public price data can differ from a broker. When the order of price touches is unclear, V2 leaves the result unresolved instead of guessing.'}
    const waitStudy=$('#evidenceView .card');if(waitStudy){const h=$('h3',waitStudy),p=$('p',waitStudy);if(h)h.textContent='An old entry zone is not automatically invalid.';if(p)p.textContent='In the historical study, many zones were revisited hours later. These percentages describe past cases; they do not predict the current setup.'}
    const glossary=$('#dataView .glossary');if(glossary){
      const defs={
        'Formation campaign':'One continuous setup in the same direction. Several liquidity sweeps can happen inside one setup.',
        'Fresh POI':'POI means point of interest. In V2, this is the new entry zone found after market structure breaks.',
        'POI lifecycle':'How long an entry zone has been waiting and whether price has touched it. Time by itself does not cancel the zone.',
        'Partial mitigation':'Price entered part of the entry zone but did not reach the midpoint used for the paper entry.',
        'Automatic paper trade':'A simulated trade created by V2 using fixed entry, stop and target rules. No real money is placed.',
        'Paper account':'A simulated $500 account. V2 risks 1% of the paper balance when a paper entry is recorded.',
        'Pip':'A small FX price unit. For EURUSD and GBPUSD, 1 pip is 0.0001.',
        'Execution evidence':'A separate check using public BID/ASK data to see whether a paper entry was also visible on a more realistic price path.',
        'Execution truth':'V2 does not have your broker’s exact fills, spread or slippage. Public BID/ASK data improves the check but is still research data.'
      };
      $$('details',glossary).forEach(d=>{const name=$('summary span:first-child',d)?.textContent?.trim(),p=$('p',d);if(name&&p&&defs[name])p.textContent=defs[name]});
    }
  }
  function accountToggle(){
    if(!mobile())return;const card=$('#paperAccount');if(!card||!$('.portfolioTop',card))return;if($('.mobileAccountToggle',card))return;
    const b=document.createElement('button');b.type='button';b.className='mobileAccountToggle';b.setAttribute('aria-expanded','false');b.innerHTML='<span>Show account details</span><span class="material-symbols-rounded" aria-hidden="true">expand_more</span>';
    b.addEventListener('click',()=>{const open=card.classList.toggle('mobileExpanded');b.setAttribute('aria-expanded',String(open));b.firstElementChild.textContent=open?'Hide account details':'Show account details';b.lastElementChild.textContent=open?'expand_less':'expand_more'});card.appendChild(b)
  }
  function plainFocus(){
    if(!mobile())return;const root=$('#focusBoard');if(!root)return;
    $$('.focusCard .label',root).forEach(el=>{const txt=el.textContent.trim().toLowerCase();if(txt.includes('watch level'))el.lastChild.textContent=' Key level';else if(txt.includes('research watch'))el.lastChild.textContent=' Setup note';else if(txt.includes('next trigger'))el.lastChild.textContent=' Next step';else if(txt.includes('context'))el.lastChild.textContent=' Bigger picture'});
    $$('.focusStep',root).forEach((el,i)=>{const b=$('b',el);if(!b)return;const names=['Sweep','Break (BOS)','Zone (POI)','Entry'];b.textContent=`${i+1}. ${names[i]}`});
    const status=$('.focusStatus',root);if(status){const map={'PAPER TRADE OPEN':'Paper trade open','WAIT FOR POI':'Wait for entry zone','POI READY':'Entry zone ready','BOS CONFIRMED':'Structure break confirmed','WATCH STRUCTURE':'Watch the setup','NO FOCUS':'No setup to act on'};status.textContent=map[status.textContent.trim()]||status.textContent.toLowerCase().replace(/\b\w/g,m=>m.toUpperCase())}
    $$('.focusCard h3,.focusCard p,.focusSummary',root).forEach(el=>{
      el.innerHTML=el.innerHTML
        .replaceAll('HTF','higher timeframes')
        .replaceAll('POI midpoint','entry-zone midpoint')
        .replaceAll('POI','entry zone (POI)')
        .replaceAll('BOS','break of structure (BOS)')
        .replaceAll('M15','15-minute')
        .replaceAll('canonical','fixed-rule')
        .replaceAll('invalidation','cancellation');
    });
  }
  function navLabels(){if(!mobile())return;const labels={overview:'Home',chartView:'Chart',tradesView:'Trades',evidenceView:'Research',dataView:'Data'};$$('.bottom [data-view]').forEach(b=>{const t=$('span:last-child',b);if(t)t.textContent=labels[b.dataset.view]||t.textContent})}
  let scheduled=false;function enhance(){if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;staticCopy();accountToggle();plainFocus();navLabels()})}
  const obs=new MutationObserver(enhance);obs.observe(document.documentElement,{subtree:true,childList:true});
  mq.addEventListener?.('change',enhance);document.addEventListener('DOMContentLoaded',enhance);enhance();
})();
