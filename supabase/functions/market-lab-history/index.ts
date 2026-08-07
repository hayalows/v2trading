import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const db=createClient(Deno.env.get('SUPABASE_URL')!,Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,{auth:{persistSession:false}});
const H={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'content-type','Content-Type':'application/json','Cache-Control':'no-store'};
Deno.serve(async(req)=>{
  if(req.method==='OPTIONS')return new Response('ok',{headers:H});
  const u=new URL(req.url),symbol=(u.searchParams.get('symbol')||'EURUSD').toUpperCase();
  if(!['EURUSD','GBPUSD'].includes(symbol))return new Response(JSON.stringify({error:'core FX only'}),{status:400,headers:H});
  const q=await db.from('market_state_history').select('as_of,reference_price,formation_stage,formation_code,formation_direction,regime,state').eq('symbol',symbol).order('as_of',{ascending:false}).limit(12);
  return new Response(JSON.stringify({symbol,history:q.data||[],error:q.error?.message||null}),{status:q.error?500:200,headers:H});
});
