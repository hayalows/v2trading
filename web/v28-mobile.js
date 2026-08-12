(()=>{
  const mq=window.matchMedia('(max-width:719px)');
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const setText=(el,text)=>{if(el&&el.textContent!==text)el.textContent=text};
  const setHtml=(el,html)=>{if(el&&el.innerHTML!==html)el.innerHTML=html};
  const copy=(selector,text)=>setText($(selector),text);
  const mobile=()=>mq.matches;
  function staticCopy(){
    if(!mobile())return;
    document.documentElement.classList.add('v28Mobile');
    copy('.brand b','V2 Market Lab');copy('.brand span','Paper trading research');
    copy('.intro .eyebrow','EURUSD · GBPUSD');copy('.intro h1','What matters right now');copy('.intro p','See the current setup, what to wait for next, and the key paper-trade levels.');
    setHtml($('.researchDisclosure>summary span:first-child'),'More market details<small>Trends, data and research</small>');
    copy('#chartView .sectionHead p','Use the chart to check the setup visually. It does not place trades.');
    copy('#tradesView .sectionHead p','See paper-trade plans, entries, stops, targets and recorded outcomes.');
    copy('#evidenceView .sectionHead p','See the research behind V2. These results describe past data; they are not trade signals.');
    copy('#dataView .sectionHead p','See how fresh the data is and where V2 has limits.');
    const chartCard=$('#chartView .card');if(chartCard){setText($('h3',chartCard),'Open Trades to see V2 levels on the chart.');setText($('p',chartCard),'The trade chart shows the entry zone (POI), entry, stop loss and target used by the paper engine.')}
    const frozen=$('#tradesView .paperWorkspace .card');if(frozen){setHtml($('.cardLabel',frozen),'<span class="material-symbols-rounded">rule</span>Paper-trade rules');setText($('h3',frozen),'Entry zone midpoint → stop → 2.5R target');setText($('p',frozen),'Entry is the middle of the entry zone (POI). The stop stays beyond the liquidity sweep. The target stays at 2.5 times the amount at risk.');setHtml($('.paperNotice',frozen),'<strong>Research only</strong>Public price data can differ from a broker. When the order of price touches is unclear, V2 leaves the result unresolved instead of guessing.')}
    const waitStudy=$('#evidenceView .card');if(waitStudy){setText($('h3',waitStudy),'An old entry zone is not automatically invalid.');setText($('p',waitStudy),'In the historical study, many zones were revisited hours later. These percentages describe past cases; they do not predict the current setup.')}
    const glossary=$('#dataView .glossary');if(glossary){const defs={'Formation campaign':'One continuous setup in the same direction. Several liquidity sweeps can happen inside one setup.','Fresh POI':'POI means point of interest. In V2, this is the new entry zone found after market structure breaks.','POI lifecycle':'How long an entry zone has been waiting and whether price has touched it. Time by itself does not cancel the zone.','Partial mitigation':'Price entered part of the entry zone but did not reach the midpoint used for the paper entry.','Automatic paper trade':'A simulated trade created by V2 using fixed entry, stop and target rules. No real money is placed.','Paper account':'A simulated $500 account. V2 risks 1% of the paper balance when a paper entry is recorded.','Pip':'A small FX price unit. For EURUSD and GBPUSD, 1 pip is 0.0001.','Execution evidence':'A separate check using public BID/ASK data to see whether a paper entry was also visible on a more realistic price path.','Execution truth':'V2 does not have your broker’s exact fills, spread or slippage. Public BID/ASK data improves the check but is still research data.'};$$('details',glossary).forEach(d=>{const name=$('summary span:first-child',d)?.textContent?.trim(),p=$('p',d);if(name&&p&&defs[name])setText(p,defs[name])})}
  }
  function accountToggle(){
    if(!mobile())return;const card=$('#paperAccount');if(!card||!$('.portfolioTop',card)||$('.mobileAccountToggle',card))return;
    const b=document.createElement('button');b.type='button';b.className='mobileAccountToggle';b.setAttribute('aria-expanded','false');b.innerHTML='<span>Show account details</span><span class="material-symbols-rounded" aria-hidden="true">expand_more</span>';
    b.addEventListener('click',()=>{const open=card.classList.toggle('mobileExpanded');b.setAttribute('aria-expanded',String(open));setText(b.firstElementChild,open?'Hide account details':'Show account details');setText(b.lastElementChild,open?'expand_less':'expand_more')});card.appendChild(b)
  }
  function plainFocus(){
    if(!mobile())return;const root=$('#focusBoard');if(!root)return;
    $$('.focusCard .label',root).forEach(el=>{if(el.dataset.v28Plain)return;const txt=el.textContent.trim().toLowerCase(),tail=el.lastChild;if(txt.includes('watch level'))setText(tail,' Key level');else if(txt.includes('research watch'))setText(tail,' Setup note');else if(txt.includes('next trigger'))setText(tail,' Next step');else if(txt.includes('context'))setText(tail,' Bigger picture');el.dataset.v28Plain='1'});
    $$('.focusStep',root).forEach((el,i)=>{if(el.dataset.v28Plain)return;const b=$('b',el),names=['Sweep','Break (BOS)','Zone (POI)','Entry'];if(b)setText(b,`${i+1}. ${names[i]}`);el.dataset.v28Plain='1'});
    const status=$('.focusStatus',root);if(status&&!status.dataset.v28Plain){const map={'PAPER TRADE OPEN':'Paper trade open','WAIT FOR POI':'Wait for entry zone','POI READY':'Entry zone ready','BOS CONFIRMED':'Structure break confirmed','WATCH STRUCTURE':'Watch the setup','NO FOCUS':'No setup to act on'};const next=map[status.textContent.trim()];if(next)setText(status,next);status.dataset.v28Plain='1'}
    $$('.focusCard h3,.focusCard p,.focusSummary',root).forEach(el=>{if(el.dataset.v28Plain)return;let h=el.innerHTML;h=h.replaceAll('HTF','higher timeframes').replaceAll('POI midpoint','entry-zone midpoint').replace(/\bPOI\b/g,'entry zone (POI)').replace(/\bBOS\b/g,'break of structure (BOS)').replace(/\bM15\b/g,'15-minute').replace(/\bcanonical\b/gi,'fixed-rule').replace(/\binvalidation\b/gi,'cancellation');setHtml(el,h);el.dataset.v28Plain='1'});
  }
  function navLabels(){if(!mobile())return;const labels={overview:'Home',chartView:'Chart',tradesView:'Trades',evidenceView:'Research',dataView:'Data'};$$('.bottom [data-view]').forEach(b=>setText($('span:last-child',b),labels[b.dataset.view]||''))}
  let scheduled=false;function enhance(){if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;staticCopy();accountToggle();plainFocus();navLabels()})}
  const obs=new MutationObserver(enhance);obs.observe(document.documentElement,{subtree:true,childList:true});
  mq.addEventListener?.('change',enhance);document.addEventListener('DOMContentLoaded',enhance);enhance();
})();
