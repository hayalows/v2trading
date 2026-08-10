import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Cache-Control": "no-store",
};
const SYMBOLS = new Set(["EURUSD", "GBPUSD"]);
const CHART_SYMBOL: Record<string,string> = { EURUSD: "EURUSD=X", GBPUSD: "GBPUSD=X" };
const MAX_ENTRY_BARS = 8;
const MAX_HOLD_BARS = 48;
const STOP_BUFFER_ATR = 0.03;
const REWARD_R = 2.5;
const MIN_RISK_ATR = 0.08;
const MAX_RISK_ATR = 1.60;
const HISTORY_RECOVERY_HOURS = 3;

type Bar = { ts:string; open:number; high:number; low:number; close:number; source?:string };
type PaperTrade = Record<string, any>;

function json(data:unknown,status=200){return new Response(JSON.stringify(data),{status,headers:{...CORS,"Content-Type":"application/json; charset=utf-8"}})}
function n(v:unknown){if(v===null||v===undefined||v==='')return null;const x=Number(v);return Number.isFinite(x)?x:null}
function isoMs(ts:string){return new Date(ts).getTime()}
function clamp(x:number,lo:number,hi:number){return Math.max(lo,Math.min(hi,x))}
function tr(bars:Bar[]){return bars.map((b,i)=>i===0?b.high-b.low:Math.max(b.high-b.low,Math.abs(b.high-bars[i-1].close),Math.abs(b.low-bars[i-1].close)))}
function rollingMean(xs:number[],period:number){const out:number[]=[];let s=0;for(let i=0;i<xs.length;i++){s+=xs[i];if(i>=period)s-=xs[i-period];out.push(s/Math.min(i+1,period))}return out}
function touches(b:Bar,p:number){return b.low<=p&&p<=b.high}
function floor15(ts:string){const ms=isoMs(ts),step=15*60_000;return new Date(Math.floor(ms/step)*step).toISOString()}

async function loadBars(symbol:string,limit=700):Promise<Bar[]>{
  const q=await db.from("market_bars").select("ts,open,high,low,close,source").eq("symbol",symbol).eq("timeframe","15m").order("ts",{ascending:false}).limit(limit);
  if(q.error)throw new Error(`bars ${symbol}: ${q.error.message}`);
  const byTs=new Map<string,Bar>();
  for(const r of (q.data??[]).reverse()){
    const o=n(r.open),h=n(r.high),l=n(r.low),c=n(r.close);
    if(o==null||h==null||l==null||c==null||o<=0||h<l)continue;
    byTs.set(new Date(r.ts).toISOString(),{ts:new Date(r.ts).toISOString(),open:o,high:h,low:l,close:c,source:r.source??undefined});
  }
  return [...byTs.values()].sort((a,b)=>isoMs(a.ts)-isoMs(b.ts));
}

async function yahoo5m(symbol:string):Promise<Bar[]>{
  const enc=encodeURIComponent(CHART_SYMBOL[symbol]);let last='';
  for(const host of ["query1.finance.yahoo.com","query2.finance.yahoo.com"]){
    try{
      const u=`https://${host}/v8/finance/chart/${enc}?interval=5m&range=5d&includePrePost=false`;
      const r=await fetch(u,{headers:{"User-Agent":"Mozilla/5.0 V2PaperResearch/1.0","Accept":"application/json"}});
      if(!r.ok){last=`${host}:${r.status}`;continue}
      const j=await r.json(),root=j?.chart?.result?.[0],q=root?.indicators?.quote?.[0]??{};if(!root?.timestamp?.length){last=`${host}:empty`;continue}
      const out:Bar[]=[];
      for(let i=0;i<root.timestamp.length;i++){
        const o=n(q.open?.[i]),h=n(q.high?.[i]),l=n(q.low?.[i]),c=n(q.close?.[i]);if(o==null||h==null||l==null||c==null||h<l)continue;
        const ts=new Date(root.timestamp[i]*1000).toISOString();if(Date.now()>=isoMs(ts)+5*60_000)out.push({ts,open:o,high:h,low:l,close:c});
      }
      return out;
    }catch(e){last=String(e)}
  }
  throw new Error(`5m fetch failed ${last}`);
}

async function eventOnce(tradeKey:string,eventType:string,eventAt:string,price:number|null,payload:any={}){
  const exists=await db.from("paper_trade_events").select("id").eq("trade_key",tradeKey).eq("event_type",eventType).limit(1).maybeSingle();
  if(exists.data)return;
  const w=await db.from("paper_trade_events").insert({trade_key:tradeKey,event_at:eventAt,event_type:eventType,price,payload});
  if(w.error)throw new Error(`event ${tradeKey}/${eventType}: ${w.error.message}`);
}

async function campaignFor(symbol:string,direction:string,sweepTime:string){
  const q=await db.from("formation_campaigns").select("campaign_key,started_at,ended_at,first_sweep_time,last_sweep_time,max_stage").eq("symbol",symbol).eq("direction",direction).order("started_at",{ascending:false}).limit(20);
  const s=isoMs(sweepTime);
  return (q.data??[]).find((r:any)=>isoMs(r.started_at)<=s&&(!r.ended_at||s<=isoMs(r.ended_at)))??null;
}

function historyState(row:any){
  const f=row?.state?.formation??{},details=f?.details??{},trends=row?.state?.trends??{};
  return {
    symbol:row.symbol,
    formation_stage:row.formation_stage,
    formation_code:row.formation_code,
    formation_direction:row.formation_direction,
    poi_low:f.poiLow,
    poi_high:f.poiHigh,
    market_session:row?.state?.session??null,
    regime:row.regime,
    d1_trend:trends?.d1?.label??null,
    h4_trend:trends?.h4?.label??null,
    h1_trend:trends?.h1?.label??null,
    m15_trend:trends?.m15?.label??null,
    details:{formation:details,diagnostics:row?.state?.diagnostics??{}},
    recovered_from_history:true,
    recovered_as_of:row.as_of,
  };
}

async function armFromState(state:any,bars:Bar[]):Promise<PaperTrade|null>{
  const stage=Number(state?.formation_stage??0),dir=state?.formation_direction;
  const form=state?.details?.formation??{};
  const sweepTime=form?.sweepTime,bosTime=form?.bosTime,poiTime=form?.poiTime;
  const low=n(state?.poi_low),high=n(state?.poi_high);
  if(stage<6||!['long','short'].includes(dir)||form?.fresh!==true||!sweepTime||!bosTime||low==null||high==null||high<=low)return null;
  const tradeKey=`${state.symbol}:${dir}:${new Date(sweepTime).toISOString()}`;
  const old=await db.from("paper_trades").select("*").eq("trade_key",tradeKey).maybeSingle();
  if(old.data)return old.data;
  const si=bars.findIndex(b=>b.ts===new Date(sweepTime).toISOString()),bi=bars.findIndex(b=>b.ts===new Date(bosTime).toISOString());
  if(si<0||bi<0||bi<=si)return null;
  const atrs=rollingMean(tr(bars),14),atr=atrs[si];if(!Number.isFinite(atr)||atr<=0)return null;
  const entry=(low+high)/2,sweepExtreme=dir==='long'?bars[si].low:bars[si].high;
  const stop=dir==='long'?sweepExtreme-STOP_BUFFER_ATR*atr:sweepExtreme+STOP_BUFFER_ATR*atr;
  const risk=dir==='long'?entry-stop:stop-entry,riskAtr=risk/atr,target=dir==='long'?entry+REWARD_R*risk:entry-REWARD_R*risk;
  const valid=risk>0&&riskAtr>=MIN_RISK_ATR&&riskAtr<=MAX_RISK_ATR;
  const camp=await campaignFor(state.symbol,dir,sweepTime);
  const row:any={
    trade_key:tradeKey,symbol:state.symbol,campaign_key:camp?.campaign_key??null,episode_key:tradeKey,direction:dir,status:valid?'armed':'invalid',
    armed_at:new Date().toISOString(),sweep_time:new Date(sweepTime).toISOString(),bos_time:new Date(bosTime).toISOString(),poi_time:poiTime?new Date(poiTime).toISOString():null,
    entry_expires_at:new Date(isoMs(bosTime)+(MAX_ENTRY_BARS+1)*15*60_000).toISOString(),poi_low:low,poi_high:high,entry_price:entry,stop_price:stop,target_price:target,
    sweep_extreme:sweepExtreme,atr_at_plan:atr,risk_distance:risk,risk_atr:riskAtr,reward_r:REWARD_R,
    context:{formation_stage:stage,formation_code:state.formation_code,market_session:state.market_session,regime:state.regime,trends:{d1:state.d1_trend,h4:state.h4_trend,h1:state.h1_trend,m15:state.m15_trend},diagnostics:state?.details?.diagnostics??{},poi_source:'live full-candle POI; midpoint paper entry',entry_rule:'first future completed M15 bar after BOS touching POI midpoint',recovered_from_history:Boolean(state.recovered_from_history),recovered_as_of:state.recovered_as_of??null,invalid_reason:valid?null:`risk_atr ${riskAtr.toFixed(3)} outside ${MIN_RISK_ATR}-${MAX_RISK_ATR}`},
  };
  const w=await db.from("paper_trades").insert(row).select("*").single();if(w.error)throw new Error(`arm ${tradeKey}: ${w.error.message}`);
  await eventOnce(tradeKey,valid?'armed':'invalid',row.armed_at,valid?entry:null,{entry,stop,target,riskAtr,poiLow:low,poiHigh:high,recoveredFromHistory:Boolean(state.recovered_from_history),reason:row.context.invalid_reason});
  return w.data;
}

function m15Hit(trade:PaperTrade,b:Bar){
  const entry=Number(trade.entry_price),stop=Number(trade.stop_price),target=Number(trade.target_price),dir=trade.direction;
  return {entry:touches(b,entry),stop:dir==='long'?b.low<=stop:b.high>=stop,target:dir==='long'?b.high>=target:b.low<=target};
}

async function resolveEntryBar5m(trade:PaperTrade,bar:Bar){
  let rows:Bar[]=[];try{rows=await yahoo5m(trade.symbol)}catch{return {kind:'ambiguous',reason:'entry bar touched an exit level and 5m public path was unavailable'}}
  const start=isoMs(bar.ts),end=start+15*60_000,sub=rows.filter(x=>isoMs(x.ts)>=start&&isoMs(x.ts)<end);
  if(!sub.length)return {kind:'ambiguous',reason:'no completed 5m bars available for entry-bar ordering'};
  let entered=false,entryAt:string|null=null;
  for(const b of sub){
    const h=m15Hit(trade,b);
    if(!entered){
      if(!h.entry)continue;
      if(h.stop||h.target)return {kind:'ambiguous',reason:'entry and exit level touched inside the same 5m bar'};
      entered=true;entryAt=b.ts;continue;
    }
    if(h.stop&&h.target)return {kind:'ambiguous',reason:'stop and target touched inside the same 5m bar after entry',entryAt};
    if(h.stop)return {kind:'loss',entryAt,exitAt:b.ts,exitPrice:Number(trade.stop_price),resolution:'5m'};
    if(h.target)return {kind:'win',entryAt,exitAt:b.ts,exitPrice:Number(trade.target_price),resolution:'5m'};
  }
  return entered?{kind:'open',entryAt:entryAt??bar.ts,resolution:'5m'}:{kind:'ambiguous',reason:'15m showed midpoint touch but 5m path did not reproduce it'};
}

async function resolveBoth5m(trade:PaperTrade,bar:Bar){
  let rows:Bar[]=[];try{rows=await yahoo5m(trade.symbol)}catch{return {kind:'ambiguous',reason:'same M15 bar touched stop and target and 5m public path was unavailable'}}
  const start=isoMs(bar.ts),end=start+15*60_000,sub=rows.filter(x=>isoMs(x.ts)>=start&&isoMs(x.ts)<end);
  if(!sub.length)return {kind:'ambiguous',reason:'no completed 5m bars available for stop/target ordering'};
  for(const b of sub){const h=m15Hit(trade,b);if(h.stop&&h.target)return {kind:'ambiguous',reason:'stop and target touched inside the same 5m bar'};if(h.stop)return {kind:'loss',exitAt:b.ts,exitPrice:Number(trade.stop_price),resolution:'5m'};if(h.target)return {kind:'win',exitAt:b.ts,exitPrice:Number(trade.target_price),resolution:'5m'}}
  return {kind:'ambiguous',reason:'15m stop/target collision was not reproducible on available 5m bars'};
}

function excursions(trade:PaperTrade,bars:Bar[],entryIdx:number,lastIdx:number){
  const xs=bars.slice(entryIdx,lastIdx+1),entry=Number(trade.entry_price),risk=Number(trade.risk_distance);if(!xs.length||risk<=0)return {mfe:null,mae:null};
  const hi=Math.max(...xs.map(x=>x.high)),lo=Math.min(...xs.map(x=>x.low));
  return trade.direction==='long'?{mfe:(hi-entry)/risk,mae:(entry-lo)/risk}:{mfe:(entry-lo)/risk,mae:(hi-entry)/risk};
}

async function finalize(trade:PaperTrade,kind:string,exitAt:string,exitPrice:number|null,resolution:string,reason:string|null,bars:Bar[],entryIdx:number,exitIdx:number){
  const ex=excursions(trade,bars,entryIdx,exitIdx),gross=kind==='win'?REWARD_R:kind==='loss'?-1:null;
  const patch:any={status:kind,exit_at:exitAt,exit_price:exitPrice,gross_r:gross,bars_held:exitIdx-entryIdx+1,mfe_r:ex.mfe,mae_r:ex.mae,resolution_timeframe:resolution,ambiguous_reason:reason,updated_at:new Date().toISOString()};
  const w=await db.from("paper_trades").update(patch).eq("trade_key",trade.trade_key);if(w.error)throw new Error(`finalize ${trade.trade_key}: ${w.error.message}`);
  await eventOnce(trade.trade_key,kind,exitAt,exitPrice,{grossR:gross,mfeR:ex.mfe,maeR:ex.mae,resolution,reason});
}

async function evaluateTrade(trade:PaperTrade,bars:Bar[]){
  const bosIdx=bars.findIndex(b=>b.ts===new Date(trade.bos_time).toISOString());if(bosIdx<0)return;
  if(trade.status==='armed'){
    const eligible=bars.slice(bosIdx+1,bosIdx+1+MAX_ENTRY_BARS);
    const k=eligible.findIndex(b=>touches(b,Number(trade.entry_price)));
    if(k<0){
      if(bars.length-1>=bosIdx+MAX_ENTRY_BARS){
        const at=eligible.at(-1)?.ts??new Date().toISOString();
        const w=await db.from("paper_trades").update({status:'expired',updated_at:new Date().toISOString()}).eq("trade_key",trade.trade_key);if(w.error)throw new Error(w.error.message);
        await eventOnce(trade.trade_key,'expired',at,null,{reason:'POI midpoint not touched within 8 future completed M15 bars after BOS'});
      }
      return;
    }
    const entryIdx=bosIdx+1+k,bar=bars[entryIdx],h=m15Hit(trade,bar),barsToEntry=entryIdx-bosIdx;
    if(h.stop||h.target){
      const r=await resolveEntryBar5m(trade,bar);
      if(r.kind==='ambiguous'){await finalize(trade,'ambiguous',bar.ts,null,'5m',r.reason,bars,entryIdx,entryIdx);return}
      const entryAt=r.entryAt??bar.ts;
      const basePatch:any={entry_at:entryAt,bars_to_entry:barsToEntry,resolution_timeframe:r.resolution??'5m',context:{...(trade.context??{}),entry_bar_resolved_5m:true},updated_at:new Date().toISOString()};
      if(r.kind==='win'||r.kind==='loss'){
        const w=await db.from("paper_trades").update({...basePatch,status:r.kind}).eq("trade_key",trade.trade_key);if(w.error)throw new Error(w.error.message);
        await eventOnce(trade.trade_key,'entry',entryAt,Number(trade.entry_price),{barsToEntry,resolution:r.resolution??'5m'});
        const refreshed={...trade,...basePatch,status:r.kind};await finalize(refreshed,r.kind,r.exitAt!,r.exitPrice!,r.resolution??'5m',null,bars,entryIdx,entryIdx);return;
      }
      const w=await db.from("paper_trades").update({...basePatch,status:'open'}).eq("trade_key",trade.trade_key);if(w.error)throw new Error(w.error.message);
      await eventOnce(trade.trade_key,'entry',entryAt,Number(trade.entry_price),{barsToEntry,resolution:r.resolution??'5m'});return;
    }
    const w=await db.from("paper_trades").update({status:'open',entry_at:bar.ts,bars_to_entry:barsToEntry,resolution_timeframe:'15m',updated_at:new Date().toISOString()}).eq("trade_key",trade.trade_key);if(w.error)throw new Error(w.error.message);
    await eventOnce(trade.trade_key,'entry',bar.ts,Number(trade.entry_price),{barsToEntry,resolution:'15m',timeSemantics:'M15 bar containing first midpoint touch; exact intra-bar entry time unknown'});
    return;
  }

  if(trade.status!=='open'||!trade.entry_at)return;
  const entryBar=floor15(trade.entry_at),entryIdx=bars.findIndex(b=>b.ts===entryBar);if(entryIdx<0)return;
  const last=Math.min(bars.length-1,entryIdx+MAX_HOLD_BARS);
  const firstEval=trade?.context?.entry_bar_resolved_5m?entryIdx+1:entryIdx;
  for(let i=firstEval;i<=last;i++){
    const h=m15Hit(trade,bars[i]);
    if(h.stop&&h.target){const r=await resolveBoth5m(trade,bars[i]);if(r.kind==='ambiguous'){await finalize(trade,'ambiguous',bars[i].ts,null,'5m',r.reason,bars,entryIdx,i);return}await finalize(trade,r.kind,r.exitAt!,r.exitPrice!,r.resolution??'5m',null,bars,entryIdx,i);return}
    if(h.stop){await finalize(trade,'loss',bars[i].ts,Number(trade.stop_price),'15m',null,bars,entryIdx,i);return}
    if(h.target){await finalize(trade,'win',bars[i].ts,Number(trade.target_price),'15m',null,bars,entryIdx,i);return}
  }
  const ex=excursions(trade,bars,entryIdx,last);
  if(bars.length-1>=entryIdx+MAX_HOLD_BARS){
    const b=bars[entryIdx+MAX_HOLD_BARS],risk=Number(trade.risk_distance),raw=trade.direction==='long'?(b.close-Number(trade.entry_price))/risk:(Number(trade.entry_price)-b.close)/risk,gross=clamp(raw,-1,REWARD_R);
    const patch={status:'timeout',exit_at:b.ts,exit_price:b.close,gross_r:gross,bars_held:MAX_HOLD_BARS+1,mfe_r:ex.mfe,mae_r:ex.mae,resolution_timeframe:'15m',updated_at:new Date().toISOString()};
    const w=await db.from("paper_trades").update(patch).eq("trade_key",trade.trade_key);if(w.error)throw new Error(w.error.message);
    await eventOnce(trade.trade_key,'timeout',b.ts,b.close,{grossR:gross,mfeR:ex.mfe,maeR:ex.mae});return;
  }
  await db.from("paper_trades").update({mfe_r:ex.mfe,mae_r:ex.mae,bars_held:last-entryIdx+1,updated_at:new Date().toISOString()}).eq("trade_key",trade.trade_key);
}

async function runEngine(){
  const states=await db.from("market_states").select("*").in("symbol",["EURUSD","GBPUSD"]);if(states.error)throw new Error(states.error.message);
  const since=new Date(Date.now()-HISTORY_RECOVERY_HOURS*3600_000).toISOString();
  const hist=await db.from("market_state_history").select("symbol,as_of,formation_stage,formation_code,formation_direction,regime,state").in("symbol",["EURUSD","GBPUSD"]).gte("formation_stage",6).gte("as_of",since).order("as_of",{ascending:false}).limit(120);if(hist.error)throw new Error(hist.error.message);
  const barCache:Record<string,Bar[]>={};
  const candidates=[...(states.data??[]),...(hist.data??[]).map(historyState)],seen=new Set<string>();
  for(const s of candidates){
    const f=s?.details?.formation??{},key=f?.sweepTime?`${s.symbol}:${s.formation_direction}:${new Date(f.sweepTime).toISOString()}`:null;
    if(key&&seen.has(key))continue;if(key)seen.add(key);
    barCache[s.symbol]??=await loadBars(s.symbol);await armFromState(s,barCache[s.symbol]);
  }
  const active=await db.from("paper_trades").select("*").in("status",["armed","open"]).order("armed_at",{ascending:true});if(active.error)throw new Error(active.error.message);
  for(const t of active.data??[]){barCache[t.symbol]??=await loadBars(t.symbol);await evaluateTrade(t,barCache[t.symbol]);}
  return {states:(states.data??[]).length,recoveredHistory:(hist.data??[]).length,evaluated:(active.data??[]).length};
}

async function snapshot(symbols:string[],includeBars:boolean){
  const trades=await db.from("paper_trades").select("*").in("symbol",symbols).order("armed_at",{ascending:false}).limit(50);if(trades.error)throw new Error(trades.error.message);
  const keys=(trades.data??[]).map((x:any)=>x.trade_key);let events:any[]=[];
  if(keys.length){const e=await db.from("paper_trade_events").select("*").in("trade_key",keys).order("event_at",{ascending:false}).limit(100);if(e.error)throw new Error(e.error.message);events=e.data??[]}
  const summary:any={};for(const s of symbols){const xs=(trades.data??[]).filter((t:any)=>t.symbol===s);summary[s]={total:xs.length,armed:xs.filter((t:any)=>t.status==='armed').length,open:xs.filter((t:any)=>t.status==='open').length,closed:xs.filter((t:any)=>['win','loss','timeout','ambiguous'].includes(t.status)).length,wins:xs.filter((t:any)=>t.status==='win').length,losses:xs.filter((t:any)=>t.status==='loss').length,latest:xs[0]??null}}
  const chartBars:any={};if(includeBars)for(const s of symbols)chartBars[s]=(await loadBars(s,180));
  return {summary,trades:trades.data??[],events,chartBars};
}

Deno.serve(async req=>{
  if(req.method==='OPTIONS')return new Response('ok',{headers:CORS});
  if(req.method!=='GET')return json({error:'GET only'},405);
  try{
    const u=new URL(req.url),raw=(u.searchParams.get('symbol')??'EURUSD,GBPUSD').split(',').map(x=>x.toUpperCase()).filter(x=>SYMBOLS.has(x)),symbols=raw.length?raw:['EURUSD','GBPUSD'];
    const shouldRun=u.searchParams.get('run')==='1',includeBars=u.searchParams.get('bars')==='1';
    const run=shouldRun?await runEngine():null,snap=await snapshot(symbols,includeBars);
    return json({version:'V2 paper-trade engine v1.3',research_only:true,broker_execution:false,generated_at:new Date().toISOString(),run,...snap,methodology:{entry:'50% live POI midpoint after fresh BOS-confirmed POI',entryWindowBars:MAX_ENTRY_BARS,stop:'sweep extreme +/- 0.03 ATR',targetR:REWARD_R,maxHoldBars:MAX_HOLD_BARS,riskAtrGate:[MIN_RISK_ATR,MAX_RISK_ATR],triggerData:'same-source completed M15 structural bars only',historyRecoveryHours:HISTORY_RECOVERY_HOURS,sameBarPolicy:'Use public 5m path when needed; otherwise mark ambiguous',executionTruth:'No broker bid/ask, spread, slippage or executable fill feed is connected. These are research paper trades.'}});
  }catch(e){return json({error:String(e)},500)}
});