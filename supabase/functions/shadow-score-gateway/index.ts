import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const db=createClient(Deno.env.get("SUPABASE_URL")!,Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,{auth:{persistSession:false}});
const ISSUER="https://token.actions.githubusercontent.com";
const AUDIENCE="v2-shadow-arena";
const REPOSITORY="hayalows/v2trading";
const WORKFLOW_REF="hayalows/v2trading/.github/workflows/v17-shadow-scorer.yml@refs/heads/main";
const CORS={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization,content-type","Access-Control-Allow-Methods":"GET,POST,OPTIONS","Cache-Control":"no-store"};
const reply=(x:unknown,status=200)=>new Response(JSON.stringify(x),{status,headers:{...CORS,"Content-Type":"application/json; charset=utf-8"}});
let jwksCache:any=null,jwksAt=0;

function bytes(s:string){const b=s.replace(/-/g,"+").replace(/_/g,"/")+"=".repeat((4-s.length%4)%4);return Uint8Array.from(atob(b),c=>c.charCodeAt(0))}
function decodeJson(s:string){return JSON.parse(new TextDecoder().decode(bytes(s)))}
async function jwks(){if(jwksCache&&Date.now()-jwksAt<6*3600_000)return jwksCache;const r=await fetch(`${ISSUER}/.well-known/jwks`);if(!r.ok)throw new Error("GitHub OIDC JWKS unavailable");jwksCache=await r.json();jwksAt=Date.now();return jwksCache}
async function authorize(req:Request){
  const auth=req.headers.get("authorization")??"";if(!auth.startsWith("Bearer "))throw new Error("missing bearer token");
  const token=auth.slice(7),parts=token.split(".");if(parts.length!==3)throw new Error("invalid JWT");
  const header=decodeJson(parts[0]),claims=decodeJson(parts[1]);if(header.alg!=="RS256"||!header.kid)throw new Error("unsupported JWT");
  const set=await jwks(),jwk=(set.keys??[]).find((k:any)=>k.kid===header.kid);if(!jwk)throw new Error("unknown OIDC key");
  const key=await crypto.subtle.importKey("jwk",jwk,{name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["verify"]);
  const ok=await crypto.subtle.verify("RSASSA-PKCS1-v1_5",key,bytes(parts[2]),new TextEncoder().encode(`${parts[0]}.${parts[1]}`));if(!ok)throw new Error("invalid OIDC signature");
  const now=Math.floor(Date.now()/1000),aud=Array.isArray(claims.aud)?claims.aud:[claims.aud];
  if(claims.iss!==ISSUER||!aud.includes(AUDIENCE))throw new Error("OIDC issuer/audience rejected");
  if(Number(claims.exp??0)<=now||Number(claims.nbf??0)>now+30)throw new Error("OIDC token expired/not active");
  if(claims.repository!==REPOSITORY||claims.ref!=="refs/heads/main")throw new Error("OIDC repository/ref rejected");
  const wf=claims.job_workflow_ref??claims.workflow_ref;if(wf!==WORKFLOW_REF)throw new Error("OIDC workflow rejected");
  if(!["schedule","workflow_dispatch","push"].includes(String(claims.event_name??"")))throw new Error("OIDC event rejected");
  return claims;
}

async function queue(){
  const q=await db.from("shadow_forecasts").select("forecast_key,symbol,observed_at,observed_bar_at,direction,landmark_age_bars,horizon_bars,status,outcome,predictions,feature_snapshot,model_spec_hash").eq("status","pending").eq("landmark_age_bars",0).is("outcome",null).order("observed_at",{ascending:true}).limit(50);
  if(q.error)throw new Error(q.error.message);
  const rows=(q.data??[]).filter((r:any)=>r?.predictions?.["granite-ttm-r2-v17"]?.p==null);
  return rows.slice(0,12);
}

async function submit(body:any){
  const scores=Array.isArray(body?.scores)?body.scores:[];let accepted=0,rejected=0;
  for(const s of scores.slice(0,24)){
    if(s?.model_version!=="granite-ttm-r2-v17"||!Number.isFinite(Number(s?.p))||Number(s.p)<=0||Number(s.p)>=1){rejected++;continue}
    const q=await db.from("shadow_forecasts").select("forecast_key,status,outcome,landmark_age_bars,predictions,observed_at,observed_bar_at").eq("forecast_key",String(s.forecast_key)).maybeSingle();
    if(q.error||!q.data||q.data.status!=="pending"||q.data.outcome!==null||Number(q.data.landmark_age_bars)!==0||q.data?.predictions?.["granite-ttm-r2-v17"]?.p!=null){rejected++;continue}
    const predictions={...(q.data.predictions??{})};
    predictions["granite-ttm-r2-v17"]={kind:"shadow",p:Number(s.p),features:s.features??{},calibratorVersion:s.calibrator_version??null,contextLastClose:s.context_last_close??null,contextSource:s.context_source??null,contextCutoff:q.data.observed_bar_at,eligibleLandmarkAgeBars:[0],scoredAt:new Date().toISOString(),preOutcome:true,visible:false};
    const w=await db.from("shadow_forecasts").update({predictions,updated_at:new Date().toISOString()}).eq("forecast_key",q.data.forecast_key).eq("status","pending").eq("landmark_age_bars",0).is("outcome",null);
    if(w.error){rejected++;continue}accepted++;
  }
  return {accepted,rejected};
}

Deno.serve(async(req:Request)=>{
  if(req.method==="OPTIONS")return new Response("ok",{headers:CORS});
  try{
    const claims=await authorize(req),url=new URL(req.url);
    if(req.method==="GET"&&url.searchParams.get("score_queue")==="1")return reply({queue:await queue(),authenticatedRepository:claims.repository,eligibleLandmarkAgeBars:[0],probabilityVisible:false});
    if(req.method==="POST")return reply(await submit(await req.json()));
    return reply({error:"unsupported operation"},405);
  }catch(e){console.error(e);return reply({error:"unauthorized or invalid request"},401)}
});
