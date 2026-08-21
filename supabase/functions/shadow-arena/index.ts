import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL=Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db=createClient(SUPABASE_URL,SERVICE_KEY,{auth:{persistSession:false}});
const CORE=["EURUSD","GBPUSD"];
async function cronOk(req:Request){const k=req.headers.get("x-v2-cron-key")??"";if(!k)return false;const q=await db.from("v2_runtime_secrets").select("secret").eq("name","cron").maybeSingle();if(q.error||!q.data?.secret)return false;const a=new TextEncoder().encode(k),b=new TextEncoder().encode(String(q.data.secret));if(a.length!==b.length)return false;let d=0;for(let i=0;i<a.length;i++)d|=a[i]!^b[i]!;return d===0}
const LANDMARKS=new Set([0,2,4,8,12,16,24]);
const HORIZON=16;
// Exact walk-forward comparator available before 2026 begins.
const BASE_P=0.1999597828272672;
const SPEC_HASH="v17-shadow-primary-h16-20260810";
const CORS={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, x-client-info, apikey, content-type","Access-Control-Allow-Methods":"GET, OPTIONS","Cache-Control":"no-store"};
const reply=(x:unknown,status=200)=>new Response(JSON.stringify(x),{status,headers:{...CORS,"Content-Type":"application/json; charset=utf-8"}});
const num=(x:unknown,f:number|null=null)=>Number.isFinite(Number(x))?Number(x):f;
const iso=(x:unknown)=>{const d=new Date(String(x));return Number.isFinite(d.getTime())?d.toISOString():null};

async function stateTwin(){
  try{
    const r=await fetch(`${SUPABASE_URL}/functions/v1/state-twin?symbol=EURUSD,GBPUSD`,{headers:{"User-Agent":"V2-Shadow-Arena/1.0"}});
    if(!r.ok)return {};
    const j=await r.json();
    return Object.fromEntries((j?.pairs??[]).map((x:any)=>[x.symbol,x]));
  }catch{return {}};
}

function barAge(c:any,state:any){
  const sweep=iso(c.first_sweep_time),bar=iso(state?.data_health?.lastM15Bar??state?.details?.dataHealth?.lastM15Bar);
  if(!sweep||!bar)return null;
  return Math.max(0,Math.round((new Date(bar).getTime()-new Date(sweep).getTime())/900000));
}

function snapshot(state:any,twin:any,campaign:any,age:number){
  const d=state?.details??{},trends=d?.trends??{},diag=d?.diagnostics??{};
  return {
    observedBeforeOutcome:true,
    market:{
      symbol:state.symbol, referencePrice:state.reference_price, structurePrice:d.structure_reference_price,
      formationStage:state.formation_stage, formationCode:state.formation_code, direction:state.formation_direction,
      regime:state.regime, rangePosition:state.range_position, atr15:state.atr15,
      bosReference:d?.formation?.bosReference??null,
      poiHigh:state.poi_high, poiLow:state.poi_low, distanceToPoiAtr:state.distance_to_poi_atr,
    },
    campaign:{campaignKey:campaign.campaign_key,startedAt:campaign.started_at,firstSweepTime:campaign.first_sweep_time,sweepCount:campaign.sweep_count,maxStage:campaign.max_stage,landmarkAgeBars:age},
    trends,
    diagnostics:diag,
    dataHealth:state.data_health,
    stateTwin:twin?{
      coherenceScore:twin?.mode?.coherenceScore,
      higherTimeframeBias:twin?.mode?.higherTimeframeBias,
      stability:twin?.stability,
      similarityScore:twin?.analog?.similarityScore,
      crossPair:twin?.crossPair,
      liveProbabilityPolicy:twin?.researchBoundary?.liveProbabilityPolicy,
    }:null,
  };
}

async function resolvePending(){
  const q=await db.from("shadow_forecasts").select("*").eq("status","pending").order("observed_at",{ascending:true}).limit(500);
  if(q.error)throw new Error(q.error.message);
  const pending=q.data??[]; if(!pending.length)return {resolved:0,pending:0};
  let resolved=0;
  for(const f of pending){
    const deadline=new Date(new Date(f.observed_bar_at).getTime()+f.horizon_bars*900000);
    const h=await db.from("market_state_history")
      .select("as_of,formation_stage,formation_direction,formation_code")
      .eq("symbol",f.symbol).gt("as_of",f.observed_at).lte("as_of",new Date(deadline.getTime()+20*60000).toISOString())
      .order("as_of",{ascending:true}).limit(200);
    if(h.error)throw new Error(`history ${f.symbol}: ${h.error.message}`);
    let event:any=null,invalid:any=null;
    for(const r of h.data??[]){
      const st=Number(r.formation_stage??0),dir=r.formation_direction;
      if(!event&&dir===f.direction&&st>=f.target_stage)event=r;
      if(!invalid&&(st<=2||(dir&&dir!==f.direction)))invalid=r;
      if(event||invalid)break;
    }
    let outcome:number|null=null, reason:string|null=null, at:string|null=null;
    if(event&&(!invalid||new Date(event.as_of)<=new Date(invalid.as_of))){outcome=1;reason=`same_direction_stage_${event.formation_stage}`;at=event.as_of}
    else if(invalid){outcome=0;reason=invalid.formation_direction&&invalid.formation_direction!==f.direction?"direction_flip":"formation_reset";at=invalid.as_of}
    else if(Date.now()>=deadline.getTime()+20*60000){outcome=0;reason="horizon_elapsed";at=deadline.toISOString()}
    if(outcome!==null){
      const w=await db.from("shadow_forecasts").update({status:"resolved",outcome,outcome_at:at,resolution_reason:reason,resolved_at:new Date().toISOString(),updated_at:new Date().toISOString()}).eq("forecast_key",f.forecast_key).eq("status","pending");
      if(w.error)throw new Error(w.error.message); resolved++;
    }
  }
  return {resolved,pending:pending.length-resolved};
}

async function capture(){
  const [states,campaigns,twins]=await Promise.all([
    db.from("market_states").select("*").in("symbol",CORE),
    db.from("formation_campaigns").select("*").eq("status","active").in("symbol",CORE),
    stateTwin(),
  ]);
  if(states.error)throw new Error(states.error.message); if(campaigns.error)throw new Error(campaigns.error.message);
  let inserted=0; const skipped:any[]=[];
  for(const state of states.data??[]){
    const c=(campaigns.data??[]).find((x:any)=>x.symbol===state.symbol&&x.direction===state.formation_direction);
    if(!c||![3,4].includes(Number(state.formation_stage))||!state.formation_direction){skipped.push({symbol:state.symbol,why:"no_active_stage_3_4_campaign"});continue}
    const lag=num(state?.data_health?.structureLagBars,999)??999;
    if(lag>1){skipped.push({symbol:state.symbol,why:"stale_structure",lagBars:lag});continue}
    const age=barAge(c,state); if(age===null||!LANDMARKS.has(age)){skipped.push({symbol:state.symbol,why:"not_landmark",ageBars:age});continue}
    const bar=iso(state?.data_health?.lastM15Bar??state?.details?.dataHealth?.lastM15Bar); if(!bar){skipped.push({symbol:state.symbol,why:"no_completed_bar"});continue}
    const twin=(twins as any)?.[state.symbol]??null;
    const key=`${state.symbol}:${c.campaign_key}:h${HORIZON}:a${age}:v17`;
    const predictions={
      "walkforward-base-v1":{kind:"probability",p:BASE_P,frozen:true},
      "state-twin-v16":{kind:"historical_candidate",p:null,status:"withheld",similarity:twin?.analog?.similarityScore??null},
      "granite-ttm-r2-v17":{kind:"shadow",p:null,status:"historical_gate_passed_live_score_pending"},
    };
    const row={forecast_key:key,symbol:state.symbol,campaign_key:c.campaign_key,observed_at:new Date().toISOString(),observed_bar_at:bar,direction:state.formation_direction,formation_stage:Number(state.formation_stage),landmark_age_bars:age,horizon_bars:HORIZON,target_stage:5,regime:state.regime,baseline_probability:BASE_P,predictions,feature_snapshot:snapshot(state,twin,c,age),model_spec_hash:SPEC_HASH,status:"pending"};
    const w=await db.from("shadow_forecasts").upsert(row,{onConflict:"forecast_key",ignoreDuplicates:true});
    if(w.error)throw new Error(w.error.message); inserted++;
  }
  return {inserted,skipped};
}

function brier(rows:any[],p=(r:any)=>Number(r.baseline_probability)){
  if(!rows.length)return null; return rows.reduce((s,r)=>s+(p(r)-Number(r.outcome))**2,0)/rows.length;
}
function logloss(rows:any[]){
  if(!rows.length)return null;return rows.reduce((s,r)=>{const p=Math.max(1e-6,Math.min(1-1e-6,Number(r.baseline_probability))),y=Number(r.outcome);return s-(y*Math.log(p)+(1-y)*Math.log(1-p))},0)/rows.length;
}
async function summary(){
  const [f,m]=await Promise.all([
    db.from("shadow_forecasts").select("forecast_key,symbol,campaign_key,observed_at,observed_bar_at,direction,formation_stage,landmark_age_bars,horizon_bars,regime,baseline_probability,predictions,status,outcome,outcome_at,resolution_reason").order("observed_at",{ascending:false}).limit(1000),
    db.from("shadow_model_registry").select("*").order("created_at",{ascending:true}),
  ]);
  if(f.error)throw new Error(f.error.message);if(m.error)throw new Error(m.error.message);
  const rows=f.data??[],resolved=rows.filter((r:any)=>r.status==="resolved"&&r.outcome!==null),pending=rows.filter((r:any)=>r.status==="pending");
  const pair=(symbol:string)=>{const rr=resolved.filter((x:any)=>x.symbol===symbol);return {resolved:rr.length,events:rr.filter((x:any)=>x.outcome===1).length,eventRate:rr.length?rr.filter((x:any)=>x.outcome===1).length/rr.length:null,baselineBrier:brier(rr)}};
  return {
    version:"V2 Shadow Arena v1.7-alpha.3",researchOnly:true,probabilityVisible:false,
    target:"Stage 3/4 → same-direction BOS / Stage 5 within 16 completed M15 bars",
    counts:{total:rows.length,pending:pending.length,resolved:resolved.length,events:resolved.filter((x:any)=>x.outcome===1).length},
    calibration:{baselineProbability:BASE_P,baselineBrier:brier(resolved),baselineLogLoss:logloss(resolved),observedEventRate:resolved.length?resolved.filter((x:any)=>x.outcome===1).length/resolved.length:null,note:"Model probabilities remain hidden. These are pre-outcome shadow records, not trade signals."},
    byPair:Object.fromEntries(CORE.map(s=>[s,pair(s)])),
    models:m.data??[],
    latest:rows.slice(0,12),
  };
}

Deno.serve(async(req:Request)=>{
  if(req.method==="OPTIONS")return new Response("ok",{headers:CORS});
  if(req.method!=="GET")return reply({error:"GET only"},405);
  try{
    const u=new URL(req.url),run=u.searchParams.get("run")==="1";
    if(run&&!(await cronOk(req)))return reply({error:"unauthorized"},401);
    let cycle:any=null;
    if(run){const resolved=await resolvePending();const captured=await capture();cycle={resolved,captured,ranAt:new Date().toISOString()}}
    return reply({...await summary(),cycle});
  }catch(e){console.error(e);return reply({error:e instanceof Error?e.message:String(e)},500)}
});
