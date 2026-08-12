import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SB=Deno.env.get("SUPABASE_URL")!,KEY=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db=createClient(SB,KEY,{auth:{persistSession:false}});
const PAIRS=["EURUSD","GBPUSD"],START=500,RISK_PCT=.01,PIP=0.0001;
const H={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization,x-client-info,apikey,content-type","Access-Control-Allow-Methods":"GET,OPTIONS","Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"};
const J=(x:any,s=200)=>new Response(JSON.stringify(x),{status:s,headers:H});
const n=(x:any)=>x===null||x===undefined||x===""?null:(Number.isFinite(Number(x))?Number(x):null);
const ts=(x:any)=>x?Date.parse(x):NaN;
const dirMove=(direction:string,from:number,to:number)=>direction==="long"?to-from:from-to;

function pipMetrics(t:any,mark:number|null){
  const entry=n(t.entry_price),stop=n(t.stop_price),target=n(t.target_price),exit=n(t.exit_price),risk=n(t.risk_distance);
  const riskPips=entry!=null&&stop!=null?Math.abs(entry-stop)/PIP:null;
  const targetPips=entry!=null&&target!=null?Math.abs(target-entry)/PIP:null;
  const realizedPips=entry!=null&&exit!=null&&["win","loss","timeout"].includes(String(t.status))?dirMove(t.direction,entry,exit)/PIP:null;
  const currentPips=t.status==="open"&&entry!=null&&mark!=null?dirMove(t.direction,entry,mark)/PIP:null;
  const currentR=t.status==="open"&&entry!=null&&mark!=null&&risk!=null&&risk>0?dirMove(t.direction,entry,mark)/risk:null;
  return{pipSize:PIP,riskPips,targetPips,realizedPips,currentPips,currentR,rewardRisk:riskPips&&targetPips?targetPips/riskPips:n(t.reward_r)??2.5};
}

Deno.serve(async(req:Request)=>{
  if(req.method==="OPTIONS")return new Response("ok",{headers:H});
  if(req.method!=="GET")return J({error:"GET only"},405);
  try{
    const[tq,sq]=await Promise.all([
      db.from("paper_trades").select("trade_key,symbol,direction,status,armed_at,entry_at,exit_at,entry_price,stop_price,target_price,exit_price,risk_distance,reward_r,gross_r,bars_held,updated_at").in("symbol",PAIRS).order("armed_at",{ascending:true}).limit(500),
      db.from("market_states").select("symbol,reference_price,as_of").in("symbol",PAIRS)
    ]);
    if(tq.error)throw new Error(tq.error.message);if(sq.error)throw new Error(sq.error.message);
    const trades=tq.data??[],marks=new Map((sq.data??[]).map((x:any)=>[x.symbol,n(x.reference_price)]));
    const events:any[]=[];
    for(const t of trades){if(t.entry_at)events.push({at:t.entry_at,kind:"entry",trade:t});if(t.exit_at)events.push({at:t.exit_at,kind:"exit",trade:t})}
    events.sort((a,b)=>ts(a.at)-ts(b.at)||(a.kind==="entry"?-1:1));
    let balance=START;const frozenRisk=new Map<string,number>(),series:any[]=[{at:null,balance:START,pnlUsd:0,label:"Start · $500 paper account"}],ledger:any[]=[];
    for(const e of events){const t=e.trade;if(e.kind==="entry"){if(!frozenRisk.has(t.trade_key))frozenRisk.set(t.trade_key,balance*RISK_PCT);continue}
      const gross=n(t.gross_r),riskUsd=frozenRisk.get(t.trade_key)??balance*RISK_PCT;
      if(gross==null){ledger.push({tradeKey:t.trade_key,symbol:t.symbol,status:t.status,at:e.at,grossR:null,riskUsd,pnlUsd:null,balanceAfter:balance,accounted:false,reason:"ambiguous/unscored outcome excluded from P&L"});continue}
      const pnl=riskUsd*gross;balance+=pnl;const row={tradeKey:t.trade_key,symbol:t.symbol,status:t.status,at:e.at,grossR:gross,riskUsd,pnlUsd:pnl,balanceAfter:balance,accounted:true};ledger.push(row);series.push({at:e.at,balance,pnlUsd:pnl,tradeKey:t.trade_key,symbol:t.symbol,grossR:gross,status:t.status})
    }
    const tradeMetrics=trades.filter((t:any)=>t.entry_at).map((t:any)=>{const mark=marks.get(t.symbol)??null,riskUsd=frozenRisk.get(t.trade_key)??null,pips=pipMetrics(t,mark),gross=n(t.gross_r);return{tradeKey:t.trade_key,symbol:t.symbol,direction:t.direction,status:t.status,entryAt:t.entry_at,exitAt:t.exit_at,riskUsd,realizedPnlUsd:gross!=null&&riskUsd!=null?riskUsd*gross:null,grossR:gross,...pips}});
    const open=tradeMetrics.filter((x:any)=>x.status==="open"),floatingPnl=open.reduce((s:number,x:any)=>s+(x.riskUsd!=null&&x.currentR!=null?x.riskUsd*x.currentR:0),0),equity=balance+floatingPnl;
    const scored=ledger.filter((x:any)=>x.accounted),ambiguous=trades.filter((t:any)=>t.status==="ambiguous").length;
    return J({version:"V2 FX Paper Account v1",generatedAt:new Date().toISOString(),researchOnly:true,brokerBalance:false,methodology:{startingBalanceUsd:START,riskPctPerEntry:RISK_PCT*100,riskFreeze:"1% of realized paper balance is frozen when a canonical entry is recorded",realization:"Only canonical numeric gross_r outcomes alter realized balance",ambiguous:"Ambiguous outcomes assign no P&L and do not alter realized balance",pipDefinition:"EURUSD/GBPUSD indicative research pip = 0.0001",executionBoundary:"Public research prices; no broker spread, slippage or executable fill truth"},account:{startingBalanceUsd:START,realizedBalanceUsd:balance,markedEquityUsd:equity,floatingPnlUsd:floatingPnl,realizedPnlUsd:balance-START,growthPct:(balance/START-1)*100,markedGrowthPct:(equity/START-1)*100,riskPct:RISK_PCT*100,scoredClosures:scored.length,wins:trades.filter((t:any)=>t.status==="win").length,losses:trades.filter((t:any)=>t.status==="loss").length,timeouts:trades.filter((t:any)=>t.status==="timeout").length,ambiguousExcluded:ambiguous,openTrades:open.length},balanceSeries:series,ledger,tradeMetrics});
  }catch(e){console.error(e);return J({error:e instanceof Error?e.message:String(e)},500)}
});
