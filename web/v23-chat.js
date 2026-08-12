(()=>{
  const ENDPOINT='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/trader-chat';
  const safe=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  const currentSymbol=()=>{if(typeof selected!=='undefined'&&selected)return selected;const a=document.querySelector('.pairSwitch .active,[data-pair].active');return (a?.textContent||'').includes('GBP')?'GBPUSD':'EURUSD'};
  let busy=false;
  function ensure(){
    let root=document.getElementById('v23Chat');
    if(root)return root;
    root=document.createElement('section');root.id='v23Chat';root.className='v23Chat';
    root.innerHTML=`<div class="v23Head"><div><div class="v23Kicker"><span class="material-symbols-rounded">forum</span>Ask V2</div><h3>Ask the research engine what is happening.</h3><p>Answers come from the current trader brief, paper state, event risk and data-trust layer.</p></div><span class="v23Live">Grounded</span></div><div class="v23Quick"><button data-q="What's happening across both pairs?">What’s happening?</button><button data-q="What is the active trade?">Active trade</button><button data-q="What happens next?">What next?</button><button data-q="What is the macro risk?">Macro risk</button><button data-q="How good is the data?">Data trust</button></div><div class="v23Messages" id="v23Messages" aria-live="polite"><div class="v23Msg bot">Ask about EURUSD, GBPUSD, the current paper trade, POI/BOS stage, macro risk, data quality or model evidence.</div></div><form class="v23Form" id="v23Form"><input id="v23Input" maxlength="800" autocomplete="off" placeholder="e.g. What is happening with EURUSD right now?" aria-label="Ask V2 a question"><button type="submit" aria-label="Send question"><span class="material-symbols-rounded">arrow_upward</span></button></form><small class="v23Boundary">Research explanation only. No broker execution feed and no live-money instruction.</small>`;
    const board=document.getElementById('v22BriefBoard')||document.getElementById('focusBoard');
    board?.insertAdjacentElement('afterend',root);
    root.querySelectorAll('[data-q]').forEach(b=>b.addEventListener('click',()=>ask(b.getAttribute('data-q')||'')));
    root.querySelector('#v23Form')?.addEventListener('submit',e=>{e.preventDefault();const input=root.querySelector('#v23Input');const q=input?.value?.trim();if(q){input.value='';ask(q)}});
    return root;
  }
  function add(text,who){const box=ensure().querySelector('#v23Messages');if(!box)return;const el=document.createElement('div');el.className=`v23Msg ${who}`;el.innerHTML=safe(text).replace(/\n/g,'<br>');box.appendChild(el);box.scrollTop=box.scrollHeight}
  async function ask(q){if(!q||busy)return;busy=true;const root=ensure(),input=root.querySelector('#v23Input'),submit=root.querySelector('.v23Form button');add(q,'user');if(input)input.disabled=true;if(submit)submit.disabled=true;const pending=document.createElement('div');pending.className='v23Msg bot loading';pending.textContent='Reading the latest V2 state…';root.querySelector('#v23Messages')?.appendChild(pending);try{const r=await fetch(ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:q,symbol:currentSymbol()}),cache:'no-store'});const x=await r.json();pending.remove();if(!r.ok)throw new Error(x.error||`Chat ${r.status}`);add(x.answer||'No answer returned.','bot')}catch(e){pending.remove();add('The chat layer could not load the latest state. The underlying research engine is unchanged; try refresh.','bot');console.warn('V2 chat',e)}finally{busy=false;if(input){input.disabled=false;input.focus()}if(submit)submit.disabled=false}}
  ensure();
})();
