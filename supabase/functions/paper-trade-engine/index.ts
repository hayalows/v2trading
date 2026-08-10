import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SB_URL=Deno.env.get("SUPABASE_URL")!;
const KEY=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db=createClient(SB_URL,KEY,{auth:{persistSession:false}});
const CORS={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization,x-client-info,apikey,content-type","Access-Control-Allow-Methods":"GET,OPTIONS","Cache-Control":"no-store"};
const SYMBOLS=["EURUSD","GBPUSD"],YAHOO:any={EURUSD:"EURUSD=X",GBPUSD:"GBPUSD=X"};
const ORIGINAL_WINDOW_BARS=8,EXTENDED_WINDOW_BARS=48,RESEARCH_TAIL_BARS=192,MAX_HOLD_BARS=48,STOP_BUFFER_ATR=0.03,REWARD_R=2.5,MIN_RISK_ATR=0.08,MAX_RISK_ATR=1.60,HISTORY_RECOVERY_HOURS=6;
type Bar={ts:string,open:number,high:number,low:number,close:number};
type Trade=Record<string,any>;

const reply=(x:any,s=200)=>new Response(JSON.stringify(x),{status:s,headers:{...CORS,"Content-Type":"application/json; charset=utf-8"}});
const num=(v:any)=>v===null||v===undefined||v===""?null:(Number.isFinite(Number(v))?Number(v):null);
const ms=(t:string)=>new Date(t).getTime();
const clamp=(x:number,a:number,b:number)=>Math.max(a,Math.min(b,x));
const touch=(b:Bar,p:number)=>b.low<=p&&p<=b.high;
const zoneTouch=(b:Bar,lo:number,hi:number)=>b.low<=hi&&b.high>=lo;
const floor15=(t:string)=>new Date(Math.floor(ms(t)/900000)*900000).toISOString();
function trueRanges(bs:Bar[]){return bs.map((b,i)=>i?Math.max(b.high-b.low,Math.abs(b.high-bs[i-1].close),Math.abs(b.low-bs[i-1].close)):b.high-b.low)}
function rollMean(xs:number[],n:number){let s=0;return xs.map((x,i)=>{s+=x;if(i>=n)s-=xs[i-n];return s/Math.min(i+1,n)})}

async function bars(symbol:string,limit=2500):Promise<Bar[]>{
  const q=await db.from("market_bars").select("ts,open,high,low,close").eq("symbol",symbol).eq("timeframe","15m").order("ts",{ascending:false}).limit(limit);
  if(q.error)throw new Error(q.error.message);
  const m=new Map<string,Bar>();
  for(const r of (q.data??[]).reverse()){
    const o=num(r.open),h=num(r.high),l=num(r.low),c=num(r.close);if(o==null||h==null||l==null||c==null||h<l)continue;
    const ts=new Date(r.ts).toISOString();m.set(ts,{ts,open:o,high:h,low:l,close:c});
  }
  return [...m.values()].sort((a,b)=>ms(a.ts)-ms(b.ts));
}

async function bars5(symbol:string):Promise<Bar[]>{
  let last="";for(const host of ["query1.finance.yahoo.com","query2.finance.yahoo.com"]){try{
    const r=await fetch(`https://${host}/v8/finance/chart/${encodeURIComponent(YAHOO[symbol])}?interval=5m&range=5d&includePrePost=false`,{headers:{"User-Agent":"Mozilla/5.0 V2PaperResearch/1.4","Accept":"application/json"}});
    if(!r.ok){last=`${host}:${r.status}`;continue}const j=await r.json(),root=j?.chart?.result?.[0],q=root?.indicators?.quote?.[0]??{};if(!root?.timestamp?.length)continue;
    const out:Bar[]=[];for(let i=0;i<root.timestamp.length;i++){const o=num(q.open?.[i]),h=num(q.high?.[i]),l=num(q.low?.[i]),c=num(q.close?.[i]);if(o==null||h==null||l==null||c==null||h<l)continue;const ts=new Date(root.timestamp[i]*1000).toISOString();if(Date.now()>=ms(ts)+300000)out.push({ts,open:o,high:h,low:l,close:c})}return out;
  }catch(e){last=String(e)}}throw new Error(`5m ${last}`);
}

async function eventOnce(k:string,type:string,at:string,price:number|null,payload:any={}){
  const e=await db.from("paper_trade_events").select("id").eq("trade_key",k).eq("event_type",type).limit(1).maybeSingle();if(e.data)return;
  const w=await db.from("paper_trade_events").insert({trade_key:k,event_at:at,event_type:type,price,payload});if(w.error)throw new Error(w.error.message);
}

function candidateCurrent(r:any){return {symbol:r.symbol,stage:r.formation_stage,code:r.formation_code,direction:r.formation_direction,low:r.poi_low,high:r.poi_high,session:r.market_session,regime:r.regime,trends:{d1:r.d1_trend,h4:r.h4_trend,h1:r.h1_trend,m15:r.m15_trend},diagnostics:r.details?.diagnostics??{},form:r.details?.formation??{},sourceAt:r.updated_at,recovered:false}}
function candidateHistory(r:any){const f=r.state?.formation??{},t=r.state?.trends??{};return {symbol:r.symbol,stage:r.formation_stage,code:r.formation_code,direction:r.formation_direction,low:f.poiLow,high:f.poiHigh,session:r.state?.session??null,regime:r.regime,trends:{d1:t.d1?.label,h4:t.h4?.label,h1:t.h1?.label,m15:t.m15?.label},diagnostics:r.state?.diagnostics??{},form:f.details??{},sourceAt:r.as_of,recovered:true}}
async function campaignKey(c:any){const q=await db.from("formation_campaigns").select("campaign_key,started_at,ended_at").eq("symbol",c.symbol).eq("direction",c.direction).order("started_at",{ascending:false}).limit(20);const s=ms(c.form.sweepTime);return (q.data??[]).find((x:any)=>ms(x.started_at)<=s&&(!x.ended_at||s<=ms(x.ended_at)))?.campaign_key??null}

async function arm(c:any,bs:Bar[]){
  const low=num(c.low),high=num(c.high),sweep=c.form?.sweepTime,bos=c.form?.bosTime,poi=c.form?.poiTime;
  if(Number(c.stage)<6||!['long','short'].includes(c.direction)||c.form?.fresh!==true||!sweep||!bos||low==null||high==null||high<=low)return null;
  const key=`${c.symbol}:${c.direction}:${new Date(sweep).toISOString()}`;
  const old=await db.from("paper_trades").select("*").eq("trade_key",key).maybeSingle();if(old.data)return old.data;
  const si=bs.findIndex(b=>b.ts===new Date(sweep).toISOString()),bi=bs.findIndex(b=>b.ts===new Date(bos).toISOString());if(si<0||bi<=si)return null;
  const atr=rollMean(trueRanges(bs),14)[si];if(!Number.isFinite(atr)||atr<=0)return null;
  const entry=(low+high)/2,extreme=c.direction==='long'?bs[si].low:bs[si].high,stop=c.direction==='long'?extreme-STOP_BUFFER_ATR*atr:extreme+STOP_BUFFER_ATR*atr;
  const risk=c.direction==='long'?entry-stop:stop-entry,riskAtr=risk/atr,target=c.direction==='long'?entry+REWARD_R*risk:entry-REWARD_R*risk,valid=risk>0&&riskAtr>=MIN_RISK_ATR&&riskAtr<=MAX_RISK_ATR;
  const now=new Date().toISOString(),row:any={trade_key:key,symbol:c.symbol,campaign_key:await campaignKey(c),episode_key:key,direction:c.direction,status:valid?'armed':'invalid',armed_at:now,sweep_time:new Date(sweep).toISOString(),bos_time:new Date(bos).toISOString(),poi_time:poi?new Date(poi).toISOString():null,entry_expires_at:null,poi_low:low,poi_high:high,entry_price:entry,stop_price:stop,target_price:target,sweep_extreme:extreme,atr_at_plan:atr,risk_distance:risk,risk_atr:riskAtr,reward_r:REWARD_R,lifecycle_phase:'fresh_wait',pending_age_bars:0,setup_condition:'intact',research_tail_bars:RESEARCH_TAIL_BARS,context:{formation_stage:c.stage,formation_code:c.code,market_session:c.session,regime:c.regime,trends:c.trends,diagnostics:c.diagnostics,recovered_from_history:c.recovered,recovered_as_of:c.recovered?c.sourceAt:null,entry_rule:'first future completed M15 bar after BOS touching POI midpoint; no time-only invalidation',v14_waiting_research:true,invalid_reason:valid?null:`risk_atr ${riskAtr.toFixed(3)} outside ${MIN_RISK_ATR}-${MAX_RISK_ATR}`}};
  const w=await db.from("paper_trades").insert(row).select("*").single();if(w.error)throw new Error(w.error.message);await eventOnce(key,valid?'armed':'invalid',now,valid?entry:null,{entry,stop,target,riskAtr,poiLow:low,poiHigh:high,recoveredFromHistory:c.recovered,reason:row.context.invalid_reason});return w.data;
}

const hits=(t:Trade,b:Bar)=>({entry:touch(b,Number(t.entry_price)),stop:t.direction==='long'?b.low<=Number(t.stop_price):b.high>=Number(t.stop_price),target:t.direction==='long'?b.high>=Number(t.target_price):b.low<=Number(t.target_price)});
async function resolve5(t:Trade,b:Bar,needsEntry:boolean){
  let xs:Bar[];try{xs=await bars5(t.symbol)}catch{return {kind:'ambiguous',reason:'5m public path unavailable'}}const start=ms(b.ts),sub=xs.filter(x=>ms(x.ts)>=start&&ms(x.ts)<start+900000);if(!sub.length)return {kind:'ambiguous',reason:'no completed 5m path'};
  let entered=!needsEntry,entryAt:string|null=needsEntry?null:t.entry_at;
  for(const x of sub){const h=hits(t,x);if(!entered){if(!h.entry)continue;if(h.stop||h.target)return {kind:'ambiguous',reason:'entry and exit level touched in same 5m bar'};entered=true;entryAt=x.ts;continue}if(h.stop&&h.target)return {kind:'ambiguous',reason:'SL and TP touched in same 5m bar',entryAt};if(h.stop)return {kind:'loss',entryAt,exitAt:x.ts,exitPrice:Number(t.stop_price)};if(h.target)return {kind:'win',entryAt,exitAt:x.ts,exitPrice:Number(t.target_price)}}return entered?{kind:'open',entryAt:entryAt??b.ts}:{kind:'ambiguous',reason:'M15 entry touch not reproduced by 5m path'};
}
function excursions(t:Trade,bs:Bar[],a:number,z:number){const x=bs.slice(a,z+1),entry=Number(t.entry_price),risk=Number(t.risk_distance);if(!x.length||risk<=0)return {mfe:null,mae:null};const hi=Math.max(...x.map(b=>b.high)),lo=Math.min(...x.map(b=>b.low));return t.direction==='long'?{mfe:(hi-entry)/risk,mae:(entry-lo)/risk}:{mfe:(entry-lo)/risk,mae:(hi-entry)/risk}}
async function finish(t:Trade,status:string,at:string,price:number|null,bs:Bar[],ei:number,xi:number,res='15m',reason:string|null=null){const ex=excursions(t,bs,ei,xi),gross=status==='win'?REWARD_R:status==='loss'?-1:null;const w=await db.from("paper_trades").update({status,lifecycle_phase:'closed',exit_at:at,exit_price:price,gross_r:gross,bars_held:xi-ei+1,mfe_r:ex.mfe,mae_r:ex.mae,resolution_timeframe:res,ambiguous_reason:reason,updated_at:new Date().toISOString()}).eq("trade_key",t.trade_key);if(w.error)throw new Error(w.error.message);await eventOnce(t.trade_key,status,at,price,{grossR:gross,mfeR:ex.mfe,maeR:ex.mae,resolution:res,reason})}

function waitingMetrics(t:Trade,bs:Bar[],bi:number){
  const seq=bs.slice(bi+1),entry=Number(t.entry_price),lo=Number(t.poi_low),hi=Number(t.poi_high),risk=Number(t.risk_distance);
  const k=seq.findIndex(b=>touch(b,entry));
  const zi=seq.findIndex(b=>zoneTouch(b,lo,hi));
  const pre=k>=0?seq.slice(0,k):seq;
  let fav=0;if(pre.length&&risk>0){const ph=Math.max(...pre.map(b=>b.high)),pl=Math.min(...pre.map(b=>b.low));fav=t.direction==='long'?(ph-entry)/risk:(entry-pl)/risk;fav=Math.max(0,fav)}
  const targetReached=fav>=REWARD_R;
  const shallow=zi>=0&&(k<0||zi<k);
  const condition=shallow&&targetReached?'partially_mitigated_after_target':shallow?'partially_mitigated':targetReached?'target_delivered_before_entry':'intact';
  const age=seq.length;
  const phase=age<=ORIGINAL_WINDOW_BARS?'fresh_wait':age<=EXTENDED_WINDOW_BARS?'extended_wait':age<=RESEARCH_TAIL_BARS?'long_tail_wait':'outside_studied_tail';
  return {seq,k,zi,age,fav,targetReached,shallow,condition,phase};
}

async function updateWaitingLifecycle(t:Trade,m:any){
  const firstZone=m.zi>=0?m.seq[m.zi]?.ts:null;
  const patch:any={status:'armed',entry_expires_at:null,lifecycle_phase:m.phase,pending_age_bars:m.age,first_zone_touch_at:t.first_zone_touch_at??firstZone,first_zone_touch_bar:t.first_zone_touch_bar??(m.zi>=0?m.zi+1:null),pre_entry_max_favorable_r:m.fav,pre_entry_target_reached:m.targetReached,setup_condition:m.condition,research_tail_bars:RESEARCH_TAIL_BARS,context:{...(t.context??{}),v14_waiting_research:true,time_only_invalidation:false,old_8_bar_window_passed:m.age>ORIGINAL_WINDOW_BARS,waiting_evidence:m.phase==='outside_studied_tail'?'outside studied 48h tail':'within studied public-proxy tail'},updated_at:new Date().toISOString()};
  const w=await db.from("paper_trades").update(patch).eq("trade_key",t.trade_key);if(w.error)throw new Error(w.error.message);
  const at=m.seq.at(-1)?.ts??new Date().toISOString();
  if(t.status==='expired')await eventOnce(t.trade_key,'reactivated_v14',at,null,{reason:'8-bar expiry removed after waiting-time study'});
  if(m.phase==='extended_wait')await eventOnce(t.trade_key,'extended_wait',at,null,{ageBars:m.age});
  if(m.phase==='long_tail_wait')await eventOnce(t.trade_key,'long_tail_wait',at,null,{ageBars:m.age});
  if(m.phase==='outside_studied_tail')await eventOnce(t.trade_key,'outside_studied_tail',at,null,{ageBars:m.age});
  if(m.shallow)await eventOnce(t.trade_key,'partially_mitigated',firstZone??at,null,{ageBars:m.zi+1});
  if(m.targetReached)await eventOnce(t.trade_key,'target_delivered_before_entry',at,Number(t.target_price),{preEntryMaxFavorableR:m.fav});
}

async function evaluate(t:Trade,bs:Bar[]){
  const bi=bs.findIndex(b=>b.ts===new Date(t.bos_time).toISOString());if(bi<0)return;
  if(t.status==='armed'||t.status==='expired'){
    const m=waitingMetrics(t,bs,bi);
    if(m.k<0){await updateWaitingLifecycle(t,m);return}
    const ei=bi+1+m.k,b=bs[ei],h=hits(t,b),barsToEntry=ei-bi;
    const base:any={status:'open',lifecycle_phase:'filled',entry_at:b.ts,bars_to_entry:barsToEntry,pending_age_bars:barsToEntry,entry_expires_at:null,first_zone_touch_at:t.first_zone_touch_at??(m.zi>=0?m.seq[m.zi]?.ts:null),first_zone_touch_bar:t.first_zone_touch_bar??(m.zi>=0?m.zi+1:null),pre_entry_max_favorable_r:m.fav,pre_entry_target_reached:m.targetReached,setup_condition:m.condition,context:{...(t.context??{}),v14_waiting_research:true,time_only_invalidation:false,old_8_bar_window_passed:barsToEntry>ORIGINAL_WINDOW_BARS},updated_at:new Date().toISOString()};
    if(h.stop||h.target){const r:any=await resolve5({...t,...base},b,true);if(r.kind==='ambiguous'){await finish({...t,...base},'ambiguous',b.ts,null,bs,ei,ei,'5m',r.reason);return}const entryAt=r.entryAt??b.ts,ctx={...base.context,entry_bar_resolved_5m:true};const w=await db.from("paper_trades").update({...base,status:r.kind==='open'?'open':r.kind,entry_at:entryAt,resolution_timeframe:'5m',context:ctx}).eq("trade_key",t.trade_key);if(w.error)throw new Error(w.error.message);await eventOnce(t.trade_key,'entry',entryAt,Number(t.entry_price),{barsToEntry,resolution:'5m',lifecyclePhase:m.phase,setupCondition:m.condition});if(r.kind==='win'||r.kind==='loss')await finish({...t,...base,context:ctx},r.kind,r.exitAt,r.exitPrice,bs,ei,ei,'5m');return}
    const w=await db.from("paper_trades").update({...base,resolution_timeframe:'15m'}).eq("trade_key",t.trade_key);if(w.error)throw new Error(w.error.message);await eventOnce(t.trade_key,'entry',b.ts,Number(t.entry_price),{barsToEntry,resolution:'15m',lifecyclePhase:m.phase,setupCondition:m.condition,timeSemantics:'M15 containing first midpoint touch'});return;
  }
  if(t.status!=='open'||!t.entry_at)return;const ei=bs.findIndex(b=>b.ts===floor15(t.entry_at));if(ei<0)return;const last=Math.min(bs.length-1,ei+MAX_HOLD_BARS),first=t.context?.entry_bar_resolved_5m?ei+1:ei;
  for(let i=first;i<=last;i++){const h=hits(t,bs[i]);if(h.stop&&h.target){const r:any=await resolve5(t,bs[i],false);if(r.kind==='ambiguous'){await finish(t,'ambiguous',bs[i].ts,null,bs,ei,i,'5m',r.reason);return}await finish(t,r.kind,r.exitAt,r.exitPrice,bs,ei,i,'5m');return}if(h.stop){await finish(t,'loss',bs[i].ts,Number(t.stop_price),bs,ei,i);return}if(h.target){await finish(t,'win',bs[i].ts,Number(t.target_price),bs,ei,i);return}}
  const ex=excursions(t,bs,ei,last);if(bs.length-1>=ei+MAX_HOLD_BARS){const b=bs[ei+MAX_HOLD_BARS],raw=t.direction==='long'?(b.close-Number(t.entry_price))/Number(t.risk_distance):(Number(t.entry_price)-b.close)/Number(t.risk_distance),gross=clamp(raw,-1,REWARD_R);const w=await db.from("paper_trades").update({status:'timeout',lifecycle_phase:'closed',exit_at:b.ts,exit_price:b.close,gross_r:gross,bars_held:MAX_HOLD_BARS+1,mfe_r:ex.mfe,mae_r:ex.mae,resolution_timeframe:'15m',updated_at:new Date().toISOString()}).eq("trade_key",t.trade_key);if(w.error)throw new Error(w.error.message);await eventOnce(t.trade_key,'timeout',b.ts,b.close,{grossR:gross,mfeR:ex.mfe,maeR:ex.mae});return}await db.from("paper_trades").update({mfe_r:ex.mfe,mae_r:ex.mae,bars_held:last-ei+1,updated_at:new Date().toISOString()}).eq("trade_key",t.trade_key);
}

async function run(){
  const current=await db.from("market_states").select("*").in("symbol",SYMBOLS);if(current.error)throw new Error(current.error.message);const since=new Date(Date.now()-HISTORY_RECOVERY_HOURS*3600000).toISOString();const hist=await db.from("market_state_history").select("symbol,as_of,formation_stage,formation_code,formation_direction,regime,state").in("symbol",SYMBOLS).gte("formation_stage",6).gte("as_of",since).order("as_of",{ascending:false}).limit(180);if(hist.error)throw new Error(hist.error.message);
  const cache:any={},seen=new Set<string>(),cands=[...(current.data??[]).map(candidateCurrent),...(hist.data??[]).map(candidateHistory)];for(const c of cands){const sw=c.form?.sweepTime,key=sw?`${c.symbol}:${c.direction}:${new Date(sw).toISOString()}`:null;if(key&&seen.has(key))continue;if(key)seen.add(key);cache[c.symbol]??=await bars(c.symbol);await arm(c,cache[c.symbol])}
  const active=await db.from("paper_trades").select("*").in("status",['armed','expired','open']).order("armed_at",{ascending:true});if(active.error)throw new Error(active.error.message);for(const t of active.data??[]){cache[t.symbol]??=await bars(t.symbol);await evaluate(t,cache[t.symbol])}return {currentStates:(current.data??[]).length,recoveredStage6Rows:(hist.data??[]).length,evaluated:(active.data??[]).length};
}
async function snapshot(symbols:string[],withBars:boolean){const q=await db.from("paper_trades").select("*").in("symbol",symbols).order("armed_at",{ascending:false}).limit(50);if(q.error)throw new Error(q.error.message);const keys=(q.data??[]).map((x:any)=>x.trade_key);let events:any[]=[];if(keys.length){const e=await db.from("paper_trade_events").select("*").in("trade_key",keys).order("event_at",{ascending:false}).limit(120);if(e.error)throw new Error(e.error.message);events=e.data??[]}const summary:any={};for(const s of symbols){const x=(q.data??[]).filter((t:any)=>t.symbol===s);summary[s]={total:x.length,armed:x.filter((t:any)=>t.status==='armed').length,open:x.filter((t:any)=>t.status==='open').length,closed:x.filter((t:any)=>['win','loss','timeout','ambiguous'].includes(t.status)).length,wins:x.filter((t:any)=>t.status==='win').length,losses:x.filter((t:any)=>t.status==='loss').length,latest:x[0]??null}}const chartBars:any={};if(withBars)for(const s of symbols)chartBars[s]=await bars(s,220);return {summary,trades:q.data??[],events,chartBars}}

Deno.serve(async req=>{if(req.method==='OPTIONS')return new Response('ok',{headers:CORS});if(req.method!=='GET')return reply({error:'GET only'},405);try{const u=new globalThis.URL(req.url),requested=(u.searchParams.get('symbol')??SYMBOLS.join(',')).split(',').map(x=>x.toUpperCase()).filter(x=>SYMBOLS.includes(x)),symbols=requested.length?requested:SYMBOLS,job=u.searchParams.get('run')==='1'?await run():null,snap=await snapshot(symbols,u.searchParams.get('bars')==='1');return reply({version:'V2 paper-trade engine v1.4',research_only:true,broker_execution:false,generated_at:new Date().toISOString(),run:job,...snap,methodology:{entry:'50% live POI midpoint after fresh BOS-confirmed POI',timeInvalidation:'None. Elapsed time changes lifecycle/evidence state but does not cancel an untouched POI.',waitingLifecycle:{freshThroughBars:ORIGINAL_WINDOW_BARS,extendedThroughBars:EXTENDED_WINDOW_BARS,studiedTailThroughBars:RESEARCH_TAIL_BARS,beyondTail:'continue tracking, label outside studied tail'},shallowPoiTouch:'Tracked as partially mitigated/degraded context; not automatic cancellation.',preEntryTargetExtension:'Tracked as context; historical public proxy did not support universal cancellation.',stop:'sweep extreme +/- 0.03 ATR',targetR:REWARD_R,maxHoldBars:MAX_HOLD_BARS,riskAtrGate:[MIN_RISK_ATR,MAX_RISK_ATR],historyRecoveryHours:HISTORY_RECOVERY_HOURS,triggerData:'same-source completed M15 structural bars only',sameBarPolicy:'public 5m when needed; otherwise ambiguous',executionTruth:'Research paper trades only; no broker bid/ask, spread, slippage or executable fill feed.'}})}catch(e){return reply({error:String(e)},500)}});