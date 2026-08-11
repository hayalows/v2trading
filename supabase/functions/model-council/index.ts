import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const db=createClient(Deno.env.get("SUPABASE_URL")!,Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,{auth:{persistSession:false}});
const CORS={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, x-client-info, apikey, content-type","Access-Control-Allow-Methods":"GET, OPTIONS","Cache-Control":"no-store"};
const reply=(x:unknown,status=200)=>new Response(JSON.stringify(x),{status,headers:{...CORS,"Content-Type":"application/json; charset=utf-8"}});
const TTM="granite-ttm-r2-v17";
const STUDENT="state-twin-student-v18";
const COUNCIL="model-council-v18";
const DISAGREE=0.15;
const num=(x:unknown)=>Number.isFinite(Number(x))?Number(x):null;

function hiddenP(row:any,model:string){return num(row?.predictions?.[model]?.p)}
function qualitative(row:any){
  const a=hiddenP(row,STUDENT),b=hiddenP(row,TTM);
  if(a===null||b===null)return "UNCALIBRATED";
  return Math.abs(a-b)>=DISAGREE?"MODEL_DISAGREEMENT":"LOW_DISAGREEMENT";
}
function brier(rows:any[],model:string){
  const q=rows.filter(r=>r.outcome!==null&&hiddenP(r,model)!==null);
  if(!q.length)return null;
  return q.reduce((s,r)=>{const p=hiddenP(r,model)!;return s+(p-Number(r.outcome))**2},0)/q.length;
}

Deno.serve(async(req:Request)=>{
  if(req.method==="OPTIONS")return new Response("ok",{headers:CORS});
  if(req.method!=="GET")return reply({error:"GET only"},405);
  try{
    const [f,m]=await Promise.all([
      db.from("shadow_forecasts").select("forecast_key,symbol,observed_at,direction,landmark_age_bars,status,outcome,resolution_reason,predictions").eq("landmark_age_bars",0).order("observed_at",{ascending:false}).limit(1000),
      db.from("shadow_model_registry").select("model_version,model_family,status,probability_visible,training_cutoff,spec_hash,metadata").in("model_version",["state-twin-v16",TTM,STUDENT,COUNCIL]),
    ]);
    if(f.error)throw new Error(f.error.message);if(m.error)throw new Error(m.error.message);
    const rows=f.data??[];
    const both=rows.filter(r=>hiddenP(r,STUDENT)!==null&&hiddenP(r,TTM)!==null);
    const resolvedBoth=both.filter(r=>r.status==="resolved"&&r.outcome!==null);
    const disagree=both.filter(r=>qualitative(r)==="MODEL_DISAGREEMENT");
    const latestBoth=both[0]??null;
    const registry=Object.fromEntries((m.data??[]).map((x:any)=>[x.model_version,x]));
    const liveMetricsUnlocked=resolvedBoth.length>=30;
    return reply({
      version:"V2 Model Council v1.8",
      researchOnly:true,
      probabilityVisible:false,
      eligibleLandmarkAgeBars:[0],
      disagreementThreshold:DISAGREE,
      decisions:{
        council:registry[COUNCIL]?.status??"not_run",
        stateTwinStudent:registry[STUDENT]?.status??"not_run",
        graniteTtm:registry[TTM]?.status??"unknown",
      },
      models:Object.values(registry).map((x:any)=>({modelVersion:x.model_version,modelFamily:x.model_family,status:x.status,probabilityVisible:false,trainingCutoff:x.training_cutoff,metadata:x.metadata})),
      prospective:{
        eligibleRecords:rows.length,
        ttmScored:rows.filter(r=>hiddenP(r,TTM)!==null).length,
        studentScored:rows.filter(r=>hiddenP(r,STUDENT)!==null).length,
        bothScored:both.length,
        resolvedBoth:resolvedBoth.length,
        modelDisagreement:disagree.length,
        disagreementRate:both.length?disagree.length/both.length:null,
        latest:latestBoth?{symbol:latestBoth.symbol,observedAt:latestBoth.observed_at,direction:latestBoth.direction,status:latestBoth.status,qualitativeState:qualitative(latestBoth)}:null,
      },
      calibration:liveMetricsUnlocked?{
        sample:resolvedBoth.length,
        ttmBrier:brier(resolvedBoth,TTM),
        studentBrier:brier(resolvedBoth,STUDENT),
        note:"Aggregate prospective calibration only. No current model probability is exposed."
      }:{sample:resolvedBoth.length,suppressed:true,unlockAt:30,note:"Aggregate live calibration remains suppressed until 30 resolved dual-scored records."},
      boundary:"No Focus ranking influence, no paper-trade influence, no broker execution claim, and no live-money execution."
    });
  }catch(e){console.error(e);return reply({error:e instanceof Error?e.message:String(e)},500)}
});
