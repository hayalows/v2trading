import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import LZMA from "npm:lzma@2.3.2";

const SB=Deno.env.get("SUPABASE_URL")!,KEY=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db=createClient(SB,KEY,{auth:{persistSession:false}});
const H={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization,x-client-info,apikey,content-type","Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"};
const J=(x:any,s=200)=>new Response(JSON.stringify(x),{status:s,headers:H});
const MAP:any={EURUSD:"EURUSD=X",GBPUSD:"GBPUSD=X"},PIP=.0001,EPS=1e-9,RR=2.5;
async function cronOk(req:Request){const k=req.headers.get("x-v2-cron-key")??"";if(!k)return false;const q=await db.from("v2_runtime_secrets").select("secret").eq("name","cron").maybeSingle();if(q.error||!q.data?.secret)return false;const a=new TextEncoder().encode(k),b=new TextEncoder().encode(String(q.data.secret));if(a.length!==b.length)return false;let d=0;for(let i=0;i<a.length;i++)d|=a[i]!^b[i]!;return d===0}
const n=(x:any)=>x===null||x===undefined||x===""?null:(Number.isFinite(Number(x))?Number(x):null);
const ms=(x:any)=>new Date(x).getTime(),floorHour=(x:number)=>Math.floor(x/3600000)*3600000,ceilMin=(x:any)=>Math.ceil(ms(x)/60000)*60000;
type Bar={ts:string,open:number,high:number,low:number,close:number};
type Tick={ts:number,ask:number,bid:number,spread:number};

function dukaPath(d:Date){return`${d.getUTCFullYear()}/${String(d.getUTCMonth()).padStart(2,"0")}/${String(d.getUTCDate()).padStart(2,"0")}/${String(d.getUTCHours()).padStart(2,"0")}h_ticks.bi5`}
async function dukaTicks(symbol:string){
  const h=floorHour(Date.now()),d=new Date(h);
  try{
    const r=await fetch(`https://datafeed.dukascopy.com/datafeed/${symbol}/${dukaPath(d)}`,{headers:{"User-Agent":"Mozilla/5.0 V2FastExecution/2.0"},signal:AbortSignal.timeout(5000)});
    if(!r.ok)return{ok:false,status:r.status,ticks:[] as Tick[]};
    const enc=new Uint8Array(await r.arrayBuffer());if(!enc.length)return{ok:false,status:204,ticks:[] as Tick[]};
    const raw:any=(LZMA as any).decompress(enc),bytes=raw instanceof Uint8Array?raw:new Uint8Array(raw),dv=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),ticks:Tick[]=[];
    for(let o=0;o+20<=bytes.length;o+=20){const ofs=dv.getUint32(o,false),ask=dv.getUint32(o+4,false)/100000,bid=dv.getUint32(o+8,false)/100000;if(!(ask>=bid&&bid>0&&ask-bid<.01))continue;ticks.push({ts:h+ofs,ask,bid,spread:(ask-bid)/PIP})}
    return{ok:ticks.length>0,status:200,ticks};
  }catch(e){return{ok:false,status:0,error:String(e),ticks:[] as Tick[]}}
}

async function yahoo1m(symbol:string){
  let last="";
  for(const host of ["query1.finance.yahoo.com","query2.finance.yahoo.com"]){try{
    const r=await fetch(`https://${host}/v8/finance/chart/${encodeURIComponent(MAP[symbol])}?interval=1m&range=1d&includePrePost=false`,{headers:{"User-Agent":"Mozilla/5.0 V2FastObserver/2.0","Accept":"application/json"},signal:AbortSignal.timeout(6000)});
    if(!r.ok){last=`${host}:${r.status}`;continue}const j=await r.json(),root=j?.chart?.result?.[0],q=root?.indicators?.quote?.[0]??{},out:Bar[]=[];
    for(let i=0;i<(root?.timestamp?.length??0);i++){const t=Number(root.timestamp[i])*1000;if(!Number.isFinite(t)||t%60000!==0||Date.now()<t+60000)continue;const o=n(q.open?.[i]),h=n(q.high?.[i]),l=n(q.low?.[i]),c=n(q.close?.[i]);if(o==null||h==null||l==null||c==null||h<l)continue;out.push({ts:new Date(t).toISOString(),open:o,high:h,low:l,close:c})}
    return out;
  }catch(e){last=String(e)}}throw new Error(`Yahoo 1m unavailable ${last}`)
}

function tickEntry(dir:string,t:Tick,e:number){return dir==="long"?t.ask<=e+EPS:t.bid>=e-EPS}
function tickExit(dir:string,t:Tick,s:number,q:number){return dir==="long"?{stop:t.bid<=s+EPS,target:t.bid>=q-EPS}:{stop:t.ask>=s-EPS,target:t.ask<=q+EPS}}
function barTouch(b:Bar,p:number){return b.low<=p+EPS&&p<=b.high+EPS}
function barExit(dir:string,b:Bar,s:number,q:number){return dir==="long"?{stop:b.low<=s+EPS,target:b.high>=q-EPS}:{stop:b.high>=s-EPS,target:b.low<=q+EPS}}

function exactPath(t:any,ticks:Tick[]){
  const e=n(t.entry_price),s=n(t.stop_price),q=n(t.target_price);if(e==null||s==null||q==null)return{kind:"invalid"};
  if(t.status==="armed"){
    const start=Math.max(ms(t.armed_at),floorHour(Date.now()));let entered:Tick|null=null;
    for(const x of ticks){if(x.ts<start)continue;if(!entered){if(!tickEntry(t.direction,x,e))continue;entered=x;const h=tickExit(t.direction,x,s,q);if(h.stop||h.target)return{kind:"ambiguous_same_tick",entry:entered};continue}const h=tickExit(t.direction,x,s,q);if(h.stop&&h.target)return{kind:"ambiguous_same_tick",entry:entered,exit:x};if(h.stop)return{kind:"loss",entry:entered,exit:x,price:s};if(h.target)return{kind:"win",entry:entered,exit:x,price:q}}
    return entered?{kind:"open",entry:entered}:{kind:"waiting"};
  }
  if(t.status==="open"&&t.entry_at){const start=Math.max(ms(t.entry_at),floorHour(Date.now()));for(const x of ticks){if(x.ts<=start)continue;const h=tickExit(t.direction,x,s,q);if(h.stop&&h.target)return{kind:"ambiguous_same_tick",exit:x};if(h.stop)return{kind:"loss",exit:x,price:s};if(h.target)return{kind:"win",exit:x,price:q}}return{kind:"tracking"}}
  return{kind:"idle"};
}

function indicativePath(t:any,bars:Bar[]){
  const e=n(t.entry_price),s=n(t.stop_price),q=n(t.target_price);if(e==null||s==null||q==null)return{kind:"invalid"};
  if(t.status==="armed"){
    const start=ceilMin(t.armed_at),seq=bars.filter(b=>ms(b.ts)>=start),i=seq.findIndex(b=>barTouch(b,e));if(i<0)return{kind:"waiting",latest:seq.at(-1)?.ts??null};const h0=barExit(t.direction,seq[i],s,q);if(h0.stop||h0.target)return{kind:"entry_candidate_ambiguous",at:seq[i].ts,latest:seq.at(-1)?.ts??null};return{kind:"entry_candidate",at:seq[i].ts,latest:seq.at(-1)?.ts??null};
  }
  if(t.status==="open"&&t.entry_at){const start=ceilMin(t.entry_at)+60000,seq=bars.filter(b=>ms(b.ts)>=start);for(const b of seq){const h=barExit(t.direction,b,s,q);if(h.stop&&h.target)return{kind:"exit_candidate_ambiguous",at:b.ts,latest:seq.at(-1)?.ts??null};if(h.stop)return{kind:"stop_candidate",at:b.ts,latest:seq.at(-1)?.ts??null};if(h.target)return{kind:"target_candidate",at:b.ts,latest:seq.at(-1)?.ts??null}}return{kind:"tracking",latest:seq.at(-1)?.ts??null}}
  return{kind:"idle"};
}

async function eventOnce(k:string,type:string,at:string,price:any,payload:any){const q=await db.from("paper_trade_events").upsert({trade_key:k,event_at:at,event_type:type,price,payload},{onConflict:"trade_key,event_type",ignoreDuplicates:true});if(q.error)throw new Error(q.error.message)}
async function hb(symbol:string,p:any){const q=await db.from("v2_fast_execution_state").upsert({symbol,updated_at:new Date().toISOString(),...p},{onConflict:"symbol"});if(q.error)throw new Error(q.error.message)}
function ctx(t:any,x:any){return{...(t.context??{}),fast_execution:{...(t.context?.fast_execution??{}),...x}}}

async function promote(t:any,r:any){
  const now=new Date().toISOString(),meta={version:"fast-paper-v2",confirmation:"Dukascopy public BID/ASK tick",brokerSpecific:false,structureRulesChanged:false,noLookahead:true,observedAt:now};
  if(r.kind==="waiting"||r.kind==="tracking"||r.kind==="idle")return{action:r.kind};
  if(r.kind==="ambiguous_same_tick"){const c=ctx(t,{...meta,lastCandidate:r.kind,candidateAt:new Date((r.exit??r.entry).ts).toISOString()});const w=await db.from("paper_trades").update({context:c,updated_at:now}).eq("trade_key",t.trade_key).eq("status",t.status);if(w.error)throw new Error(w.error.message);return{action:r.kind}}
  if(t.status==="armed"&&r.entry){const entryAt=new Date(r.entry.ts).toISOString(),c=ctx(t,{...meta,entryConfirmed:true,entryAt,entrySpreadPips:r.entry.spread,outcome:r.kind});const patch:any={status:r.kind==="open"?"open":r.kind,entry_at:entryAt,resolution_timeframe:"bidask_tick_live",context:c,updated_at:now,lifecycle_phase:r.kind==="open"?"filled":"closed",focus_active:r.kind==="open"};if(r.kind==="win"||r.kind==="loss"){patch.exit_at=new Date(r.exit.ts).toISOString();patch.exit_price=r.price;patch.gross_r=r.kind==="win"?RR:-1}const w=await db.from("paper_trades").update(patch).eq("trade_key",t.trade_key).eq("status","armed").select("trade_key,status").maybeSingle();if(w.error)throw new Error(w.error.message);if(!w.data)return{action:"race_skipped"};await eventOnce(t.trade_key,"fast_entry",entryAt,Number(t.entry_price),meta);if(r.kind==="win"||r.kind==="loss")await eventOnce(t.trade_key,`fast_${r.kind}`,new Date(r.exit.ts).toISOString(),r.price,{...meta,grossR:r.kind==="win"?RR:-1});return{action:r.kind==="open"?"opened_bidask":`closed_bidask_${r.kind}`,entryAt}}
  if(t.status==="open"&&(r.kind==="win"||r.kind==="loss")&&r.exit){const exitAt=new Date(r.exit.ts).toISOString(),c=ctx(t,{...meta,exitConfirmed:true,exitAt,outcome:r.kind});const w=await db.from("paper_trades").update({status:r.kind,lifecycle_phase:"closed",focus_active:false,exit_at:exitAt,exit_price:r.price,gross_r:r.kind==="win"?RR:-1,resolution_timeframe:"bidask_tick_live",context:c,updated_at:now}).eq("trade_key",t.trade_key).eq("status","open").select("trade_key,status").maybeSingle();if(w.error)throw new Error(w.error.message);if(!w.data)return{action:"race_skipped"};await eventOnce(t.trade_key,`fast_${r.kind}`,exitAt,r.price,{...meta,grossR:r.kind==="win"?RR:-1});return{action:`closed_bidask_${r.kind}`,exitAt}}
  return{action:r.kind};
}

async function run(){
  const q=await db.from("paper_trades").select("*").eq("focus_active",true).in("status",["armed","open"]).in("symbol",["EURUSD","GBPUSD"]).order("armed_at");if(q.error)throw new Error(q.error.message);const active=q.data??[],actions:any[]=[];
  for(const symbol of ["EURUSD","GBPUSD"]){const trades=active.filter((t:any)=>t.symbol===symbol);if(!trades.length){await hb(symbol,{status:"idle",source:"Dukascopy BID/ASK → Yahoo 1m observer fallback",latest_bar:null,active_trade_key:null,active_trade_status:null,last_action:"idle",last_action_at:new Date().toISOString(),provider_status:"idle",details:{structureRulesChanged:false}});continue}
    const d=await dukaTicks(symbol);let y:Bar[]|null=null;if(!d.ok){try{y=await yahoo1m(symbol)}catch{y=null}}
    for(const t of trades){let action:any,latest:any=null,details:any={structureRulesChanged:false,brokerExecutionTruth:false};if(d.ok){const ex=exactPath(t,d.ticks);action=await promote(t,ex);latest=d.ticks.length?new Date(d.ticks.at(-1)!.ts).toISOString():null;details={...details,confirmation:"public BID/ASK tick",spreadPips:d.ticks.at(-1)?.spread??null};await hb(symbol,{status:"active",source:"Dukascopy public BID/ASK ticks",latest_bar:latest,active_trade_key:t.trade_key,active_trade_status:t.status,last_action:action.action,last_action_at:new Date().toISOString(),provider_status:"bidask_ok",details});}
      else{const ind=y?indicativePath(t,y):{kind:"provider_unavailable"};action={action:ind.kind};latest=(ind as any).latest??y?.at(-1)?.ts??null;details={...details,confirmation:"indicative only",bidAskStatus:d.status||"unavailable",candidateAt:(ind as any).at??null};await hb(symbol,{status:y?"observing":"degraded",source:y?"Yahoo Finance public completed 1m (indicative only)":"No fast provider available",latest_bar:latest,active_trade_key:t.trade_key,active_trade_status:t.status,last_action:ind.kind,last_action_at:new Date().toISOString(),provider_status:y?"mid_fallback":"error",details});}
      actions.push({symbol,tradeKey:t.trade_key,tradeStatus:t.status,provider:d.ok?"bidask":"mid_fallback",...action,latest});
    }
  }
  return{active:active.length,actions};
}

async function replay(k:string){
  const tq=await db.from("paper_trades").select("*").eq("trade_key",k).maybeSingle();if(tq.error)throw new Error(tq.error.message);const t=tq.data;if(!t)throw new Error("trade not found");const start=t.armed_at,end=t.exit_at??new Date().toISOString();const mq=await db.from("fx_microstructure_1m").select("ts,bid_high,bid_low,ask_high,ask_low,spread_mean_pips,tick_count").eq("symbol",t.symbol).gte("ts",start).lte("ts",end).order("ts");if(mq.error)throw new Error(mq.error.message);const e=Number(t.entry_price),s=Number(t.stop_price),q=Number(t.target_price);let entered:any=null,outcome="not_filled",exit:any=null;for(const b of mq.data??[]){if(!entered){const hit=t.direction==="long"?Number(b.ask_low)<=e:Number(b.bid_high)>=e;if(!hit)continue;entered=b;continue}const h=t.direction==="long"?{stop:Number(b.bid_low)<=s,target:Number(b.bid_high)>=q}:{stop:Number(b.ask_high)>=s,target:Number(b.ask_low)<=q};if(h.stop&&h.target){outcome="ambiguous_exit_minute";exit=b;break}if(h.stop){outcome="loss";exit=b;break}if(h.target){outcome="win";exit=b;break}}if(entered&&!exit)outcome="open_or_unresolved";return{tradeKey:k,symbol:t.symbol,direction:t.direction,canonical:{status:t.status,entryAt:t.entry_at,exitAt:t.exit_at,resolution:t.resolution_timeframe},bidAskReplay:{minutes:(mq.data??[]).length,entryAt:entered?.ts??null,entrySpreadPips:entered?.spread_mean_pips??null,outcome,exitAt:exit?.ts??null},boundary:"Stored public BID/ASK minute bars are indicative research data, not broker-specific fill truth."};
}

Deno.serve(async(req)=>{if(req.method==="OPTIONS")return new Response("ok",{headers:H});if(req.method!=="GET")return J({error:"GET only"},405);try{const u=new URL(req.url),k=u.searchParams.get("trade_key");if(k)return J({ok:true,version:"fast-paper-v2",replay:await replay(k)});const wantRun=u.searchParams.get("run")==="1";if(wantRun&&!(await cronOk(req)))return J({ok:false,error:"unauthorized"},401);const rr=wantRun?await run():null;const s=await db.from("v2_fast_execution_state").select("*").order("symbol");if(s.error)throw new Error(s.error.message);return J({ok:true,version:"fast-paper-v2",generatedAt:new Date().toISOString(),researchOnly:true,structure:"completed M15 only",fastExecution:"public BID/ASK ticks when reachable",fallback:"completed public 1m observation only; cannot change paper P&L",brokerExecution:false,run:rr,states:s.data??[],boundary:"Fast execution can act only on an already-frozen V2 paper plan. It cannot create or modify sweep, BOS, POI, direction, stop or target."})}catch(e){console.error(e);return J({ok:false,error:e instanceof Error?e.message:String(e)},500)}});
