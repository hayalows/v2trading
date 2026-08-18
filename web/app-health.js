(()=>{
'use strict';
const BASE='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/';
const BUILD='V2 UI health.3 · audit.1 · 2026-08-18';
const CORE_REFRESH_MS=60000,HEALTH_REFRESH_MS=30000;
const $=s=>document.querySelector(s);
let health=null,lastHealthAt=0,lastCoreKick=Date.now(),lastCoreSuccessAt=0,coreServices={},healthBusy=false;
let observer=null;
const age=v=>{if(!v)return null;const x=Math.max(0,(Date.now()-new Date(v).getTime())/60000);return Number.isFinite(x)?x:null};
const ageText=v=>{const x=typeof v==='number'?v:age(v);if(x==null)return'—';if(x<1)return'<1m';if(x<60)return`${Math.round(x)}m`;return`${Math.floor(x/60)}h ${Math.round(x%60)}m`};
const time=v=>{if(!v)return'—';const d=new Date(v);return Number.isNaN(d.valueOf())?'—':d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})};
const short=s=>String(s??'').replace(/\s+/g,' ').slice(0,72);
function row(label,value,ok=null){const cls=ok===true?'ok':ok===false?'bad':'';return `<div class="service"><span>${label}</span><b class="${cls}">${value}</b></div>`}
function captureCore(){const root=$('#services');if(!root)return;const found={};root.querySelectorAll('.service').forEach(el=>{const label=el.querySelector('span')?.textContent?.trim(),value=el.querySelector('b')?.textContent?.trim();if(label&&value)found[label]=value});const keys=['EURUSD market state','GBPUSD market state','Paper trade engine','Portfolio snapshot'];const hits=keys.filter(k=>found[k]);if(hits.length<3)return;coreServices=found;const ok=hits.filter(k=>/^OK\b/.test(found[k])).length;if(hits.length===4&&ok===4)lastCoreSuccessAt=Date.now()}
function job(name){return(health?.jobs||[]).find(x=>x.name===name)||null}
function market(sym){return(health?.market||[]).find(x=>x.symbol===sym)||null}
function browserErrorRow(){const errors=Array.isArray(window.__v2BrowserErrors)?window.__v2BrowserErrors:[];if(!errors.length)return row('Browser JavaScript','0 errors',true);const e=errors[errors.length-1];return row('Browser JavaScript',`${errors.length} · ${short(e.message||e.reason||'error')}`,false)}
function render(){
  const root=$('#services');if(!root)return;
  captureCore();
  const eur=market('EURUSD'),gbp=market('GBPUSD'),paperJob=job('v2-paper-trade-engine-5m'),discordJob=job('v2-discord-fx-pulse-2m'),closureJob=job('v2-discord-fx-closures-5m'),qualityJob=job('v2-discord-quality-2m'),v34=job('v34-market-intelligence'),v35=job('v35-trend-candle-engine-1m');
  const coreKeys=['EURUSD market state','GBPUSD market state','Paper trade engine','Portfolio snapshot'],coreVals=coreKeys.map(k=>coreServices[k]).filter(Boolean),coreOk=coreVals.length?coreVals.filter(v=>/^OK\b/.test(v)).length:null;
  const coreText=lastCoreSuccessAt?`${time(lastCoreSuccessAt)} · ${coreOk??'—'}/4 OK`:'waiting for first refresh';
  const discord=health?.discord,audit=health?.executionAudit;
  const marketHealthy=Boolean(eur&&gbp&&eur.status==='healthy'&&gbp.status==='healthy');
  const marketAge=Math.max(Number(eur?.stateAgeMinutes||0),Number(gbp?.stateAgeMinutes||0));
  const paperHealthy=paperJob?.status==='healthy';
  const discordHealthy=discord?.status==='healthy';
  const portfolioValue=coreServices['Portfolio snapshot']||'checking…';
  const portfolioHealthy=coreServices['Portfolio snapshot']?/^OK\b/.test(coreServices['Portfolio snapshot']):null;
  const overallHealthy=health?.overall==='healthy';
  const summaryTitle=health?(overallHealthy?'All core systems healthy':'System attention needed'):'Checking system health';
  const summaryMeta=health?.generatedAt?`Updated ${time(health.generatedAt)}`:'Live diagnostic snapshot';
  const primary=[
    row('UI + navigation','READY',true),
    marketHealthy?row('Market data',`2/2 healthy · ${ageText(marketAge)} old`,true):row('Market data',eur||gbp?'ATTENTION':'checking…',eur||gbp?false:null),
    paperJob?row('Paper engine',`${paperJob.status.toUpperCase()} · every 1m · ${ageText(paperJob.lastRunAgeMinutes)} ago`,paperHealthy):row('Paper engine','checking…',null),
    row('Portfolio',portfolioValue,portfolioHealthy),
    discord?row('Discord',`${discord.status.toUpperCase()} · heartbeat ${ageText(discord.heartbeatAgeMinutes)} old`,discordHealthy):row('Discord','checking…',null)
  ];
  const advanced=[
    row('Frontend build',BUILD,true),
    browserErrorRow(),
    row('Core UI refresh',coreText,lastCoreSuccessAt>0),
    eur?row('EURUSD completed-M15',`${eur.status.toUpperCase()} · Stage ${eur.formationStage??'—'} · ${ageText(eur.stateAgeMinutes)} old`,eur.status==='healthy'):row('EURUSD completed-M15','checking…',null),
    gbp?row('GBPUSD completed-M15',`${gbp.status.toUpperCase()} · Stage ${gbp.formationStage??'—'} · ${ageText(gbp.stateAgeMinutes)} old`,gbp.status==='healthy'):row('GBPUSD completed-M15','checking…',null),
    discord?row('Last Discord alert',discord.lastAlertSentAt?`${discord.lastAlertSymbol||''} ${String(discord.lastAlertType||'').replaceAll('_',' ')} · ${time(discord.lastAlertSentAt)}`:'No alert sent yet',true):row('Last Discord alert','checking…',null),
    audit?row('Execution audit',`${audit.audited_trades??0} audited · ${audit.confirmed_entries??0} entries confirmed · ${ageText(audit.latest_audit_at)} old`,true):row('Execution audit','checking…',null),
    discordJob&&closureJob&&qualityJob?row('Discord schedulers',[discordJob,closureJob,qualityJob].every(x=>x.status==='healthy')?'3/3 HEALTHY':'ATTENTION',[discordJob,closureJob,qualityJob].every(x=>x.status==='healthy')):row('Discord schedulers','checking…',null),
    v34&&v35?row('Research schedulers',`${v34.status==='healthy'?'V3.4 OK':'V3.4 attention'} · ${v35.status==='healthy'?'V3.5 OK':'V3.5 attention'}`,v34.status==='healthy'&&v35.status==='healthy'):row('Research schedulers','checking…',null),
    health?row('Health snapshot',`${String(health.overall||'unknown').toUpperCase()} · ${time(health.generatedAt)}`,overallHealthy):row('Health snapshot','checking…',null)
  ];
  const html=`<div class="healthSummary"><div class="healthSummaryText"><span>${summaryMeta}</span><strong>${summaryTitle}</strong></div><span class="healthSummaryState ${health?(overallHealthy?'ok':'bad'):''}">${health?String(health.overall||'unknown').toUpperCase():'CHECKING'}</span></div><div class="healthCore">${primary.join('')}</div><details class="healthAdvanced"><summary>Advanced diagnostics <span>${advanced.length} checks</span></summary><div class="healthAdvancedBody">${advanced.join('')}</div></details>`;
  if(observer)observer.disconnect();root.innerHTML=html;if(observer)observer.observe(root,{childList:true,subtree:true});
}
async function loadHealth(){if(healthBusy)return;healthBusy=true;const c=new AbortController(),t=setTimeout(()=>c.abort(),5500);try{const r=await fetch(BASE+'v2-health',{cache:'no-store',signal:c.signal});if(!r.ok)throw new Error(`health HTTP ${r.status}`);health=await r.json();lastHealthAt=Date.now();render()}catch(e){health={...(health||{}),overall:'attention'};render()}finally{clearTimeout(t);healthBusy=false}}
function kickCore(){const btn=$('#refresh');if(document.visibilityState!=='visible'||!btn||btn.disabled)return;lastCoreKick=Date.now();btn.click()}
function setupObserver(){const root=$('#services');if(!root)return;observer=new MutationObserver(()=>{captureCore();render()});observer.observe(root,{childList:true,subtree:true})}
setupObserver();
window.addEventListener('v2:browser-error',()=>render());
const refresh=$('#refresh');if(refresh)refresh.addEventListener('click',()=>{lastCoreKick=Date.now();setTimeout(loadHealth,900)});
window.addEventListener('v2:view',e=>{if(e.detail?.id==='system'&&Date.now()-lastHealthAt>10000)loadHealth()});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){if(Date.now()-lastHealthAt>HEALTH_REFRESH_MS)loadHealth();if(Date.now()-lastCoreKick>CORE_REFRESH_MS)kickCore()}});
setInterval(()=>{if(document.visibilityState==='visible'&&Date.now()-lastHealthAt>=HEALTH_REFRESH_MS)loadHealth()},10000);
setInterval(()=>{if(document.visibilityState==='visible'&&Date.now()-lastCoreKick>=CORE_REFRESH_MS)kickCore()},10000);
setTimeout(loadHealth,350);
})();
