import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SB=Deno.env.get("SUPABASE_URL")!,KEY=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db=createClient(SB,KEY,{auth:{persistSession:false}});
const H={"Access-Control-Allow-Origin":"*","Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"};
const R=(x:any,s=200)=>new Response(JSON.stringify(x),{status:s,headers:H});
const CUTOFF=new Date("2026-08-12T09:30:00.000Z").getTime();
const START_EQUITY=500, RISK_PCT=.01, REWARD_R=2.5;
const POLICIES:any={
  timeout_48:{timeout:48},timeout_96:{timeout:96},timeout_192:{timeout:192},hold_sltp:{},
  be_075:{trigger:.75},be_100:{trigger:1},be_125:{trigger:1.25},be_150:{trigger:1.5},
  p25_100_be:{trigger:1,partial:.25},p33_100_be:{trigger:1,partial:.33},p50_100_be:{trigger:1,partial:.5},
  p25_150_be:{trigger:1.5,partial:.25},p33_150_be:{trigger:1.5,partial:.33},p50_150_be:{trigger:1.5,partial:.5}
};
const num=(x:any)=>Number.isFinite(Number(x))?Number(x):null;
const level=(dir:string,e:number,r:number,k:number)=>dir==="long"?e+k*r:e-k*r;
const rNow=(dir:string,e:number,r:number,m:number)=>dir==="long"?(m-e)/r:(e-m)/r;
function sim(t:any,bars:any[],mark:number|null,name:string,cfg:any){
  const e=num(t.entry_price),sl=num(t.stop_price),tp=num(t.target_price),risk=num(t.risk_distance);
  if(e==null||sl==null||tp==null||risk==null||risk<=0)return null;
  const dir=String(t.direction),triggerR=num(cfg.trigger),partial=num(cfg.partial)??0,trigger=triggerR==null?null:level(dir,e,risk,triggerR);
  let active=false,realized=0,remaining=1,status="open",gross:null|number=null,exitAt:any=null,exitPrice:any=null,amb:any=null,lastAt:any=null,barsHeld=0;
  const usable=bars.filter(b=>new Date(b.ts).getTime()>=new Date(t.entry_at).getTime());
  for(let i=0;i<usable.length;i++){
    const b=usable[i],lo=Number(b.low),hi=Number(b.high);lastAt=b.ts;barsHeld=i+1;
    const hitOrig=dir==="long"?lo<=sl:hi>=sl,hitBe=dir==="long"?lo<=e:hi>=e,hitTp=dir==="long"?hi>=tp:lo<=tp;
    const hitTrig=trigger!=null&&!active&&(dir==="long"?hi>=trigger:lo<=trigger);
    if(!active){
      if(hitOrig&&(hitTp||hitTrig)){status="ambiguous";amb="M15 stop and favorable threshold share a completed candle";exitAt=b.ts;break}
      if(hitOrig){status="loss";gross=-1;exitAt=b.ts;exitPrice=sl;break}
      if(hitTp){if(triggerR!=null&&partial>0){realized=partial*triggerR;remaining=1-partial;gross=realized+remaining*REWARD_R}else gross=REWARD_R;status="target";exitAt=b.ts;exitPrice=tp;break}
      if(hitTrig){if(hitBe){status="ambiguous";amb="M15 break-even trigger and return-to-entry share a completed candle";exitAt=b.ts;break}active=true;if(partial>0){realized=partial*(triggerR as number);remaining=1-partial}}
    }else{
      if(hitBe&&hitTp){status="ambiguous";amb="M15 break-even and target share a completed candle";exitAt=b.ts;break}
      if(hitBe){gross=realized;status=partial>0?"partial_then_be":"breakeven";exitAt=b.ts;exitPrice=e;break}
      if(hitTp){gross=realized+remaining*REWARD_R;status=partial>0?"partial_then_target":"target_after_be";exitAt=b.ts;exitPrice=tp;break}
    }
    // Canonical paper engine checks the bar at entry-array-index + MAX_HOLD_BARS.
    // Because completed-bar feeds can contain gaps, count observed bars rather than wall-clock minutes.
    if(cfg.timeout&&i>=Number(cfg.timeout)){const close=Number(b.close),raw=rNow(dir,e,risk,close);gross=realized+remaining*Math.max(-1,Math.min(REWARD_R,raw));status="timeout";exitAt=b.ts;exitPrice=close;break}
  }
  const currentBase=mark!=null?rNow(dir,e,risk,mark):null;
  const current=status==="open"&&currentBase!=null?realized+remaining*currentBase:gross;
  return {status,gross,current,active,realized,remaining,exitAt,exitPrice,amb,lastAt,barsHeld,triggerR,partial};
}
function portfolio(rows:any[],policy:string,prospectiveOnly=false){
  const x=rows.filter(r=>r.policy===policy&&(!prospectiveOnly||r.prospective));let realized=START_EQUITY,equity=START_EQUITY,closed=0,open=0;
  for(const r of x){if(num(r.gross_r)!=null){realized*=Math.max(.000001,1+RISK_PCT*Number(r.gross_r));closed++}}
  equity=realized;for(const r of x){if(r.status==="open"&&num(r.current_r)!=null){equity*=Math.max(.000001,1+RISK_PCT*Number(r.current_r));open++}}
  return {policy,startingEquity:START_EQUITY,riskPct:RISK_PCT,realizedBalance:realized,markedEquity:equity,closed,open,n:x.length};
}
Deno.serve(async req=>{
  if(req.method==="OPTIONS")return new Response("ok",{headers:H});if(!["GET","POST"].includes(req.method))return R({error:"GET/POST only"},405);
  try{
    const tr=await db.from("paper_trades").select("trade_key,symbol,direction,status,armed_at,entry_at,entry_price,stop_price,target_price,risk_distance,reward_r").in("symbol",["EURUSD","GBPUSD"]).not("entry_at","is",null).order("entry_at",{ascending:true}).limit(200);if(tr.error)throw Error(tr.error.message);const trades=tr.data??[];
    const states=await db.from("market_states").select("symbol,reference_price,as_of").in("symbol",["EURUSD","GBPUSD"]);if(states.error)throw Error(states.error.message);const marks:any={};for(const s of states.data??[])marks[s.symbol]=num(s.reference_price);
    const minEntry=trades.length?trades[0].entry_at:new Date().toISOString();const br=await db.from("market_bars").select("symbol,ts,open,high,low,close").in("symbol",["EURUSD","GBPUSD"]).eq("timeframe","15m").gte("ts",minEntry).order("ts",{ascending:true}).limit(10000);if(br.error)throw Error(br.error.message);const by:any={EURUSD:[],GBPUSD:[]};for(const b of br.data??[])by[b.symbol]?.push(b);
    const up:any[]=[];for(const t of trades){const prospective=new Date(t.armed_at).getTime()>=CUTOFF;for(const [name,cfg] of Object.entries(POLICIES)){const s=sim(t,by[t.symbol]??[],marks[t.symbol]??null,name,cfg);if(!s)continue;up.push({shadow_key:`${t.trade_key}:${name}`,trade_key:t.trade_key,symbol:t.symbol,direction:t.direction,policy:name,policy_version:"v2.4",prospective,frozen_at:t.entry_at,entry_at:t.entry_at,entry_price:t.entry_price,stop_price:t.stop_price,target_price:t.target_price,risk_distance:t.risk_distance,trigger_r:s.triggerR,partial_fraction:s.partial,status:s.status,be_active:s.active,realized_partial_r:s.realized,remaining_fraction:s.remaining,current_r:s.current,gross_r:s.gross,exit_at:s.exitAt,exit_price:s.exitPrice,bars_held:s.barsHeld,ambiguity_reason:s.amb,last_bar_at:s.lastAt,metadata:{source:"completed M15 research bars",executionTruth:false},updated_at:new Date().toISOString()})}}
    if(up.length){const q=await db.from("exit_policy_shadow").upsert(up,{onConflict:"shadow_key"});if(q.error)throw Error(q.error.message)}
    const all=await db.from("exit_policy_shadow").select("*").order("entry_at",{ascending:true});if(all.error)throw Error(all.error.message);const rows=all.data??[];const accounts=Object.keys(POLICIES).map(p=>portfolio(rows,p,false)),prospectiveAccounts=Object.keys(POLICIES).map(p=>portfolio(rows,p,true));
    return R({version:"V2.4 policy shadow",generatedAt:new Date().toISOString(),researchOnly:true,config:{startingEquity:START_EQUITY,baselineRiskPct:RISK_PCT,riskScalingEnabled:false,prospectiveCutoff:new Date(CUTOFF).toISOString()},current:{holdSlTp:accounts.find(x=>x.policy==="hold_sltp"),timeout48:accounts.find(x=>x.policy==="timeout_48")},accounts,prospectiveAccounts,rows:rows.slice(-80),boundary:"Completed public M15 bars are not broker bid/ask execution truth; ambiguous same-candle ordering is not guessed."})
  }catch(e){console.error(e);return R({error:e instanceof Error?e.message:String(e)},500)}
});