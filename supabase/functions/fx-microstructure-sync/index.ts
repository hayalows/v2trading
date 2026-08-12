import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import LZMA from "npm:lzma@2.3.2";

const U=Deno.env.get("SUPABASE_URL")!,K=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db=createClient(U,K,{auth:{persistSession:false}});
const SYMBOLS=["EURUSD","GBPUSD"],PIP=.0001,SRC="Dukascopy BID/ASK ticks";
const H={"content-type":"application/json; charset=utf-8","cache-control":"no-store"};
const J=(x:any,s=200)=>new Response(JSON.stringify(x),{status:s,headers:H});

type M={symbol:string;ts:string;bid_open:number;bid_high:number;bid_low:number;bid_close:number;ask_open:number;ask_high:number;ask_low:number;ask_close:number;spread_open_pips:number;spread_high_pips:number;spread_low_pips:number;spread_close_pips:number;spread_mean_pips:number;tick_count:number;ask_volume:number;bid_volume:number;source:string};
function path(d:Date){return`${d.getUTCFullYear()}/${String(d.getUTCMonth()).padStart(2,"0")}/${String(d.getUTCDate()).padStart(2,"0")}/${String(d.getUTCHours()).padStart(2,"0")}h_ticks.bi5`}
function decode(raw:any){return raw instanceof Uint8Array?raw:new Uint8Array(raw)}
async function fetchHour(symbol:string,d:Date){
  const url=`https://datafeed.dukascopy.com/datafeed/${symbol}/${path(d)}`;let last:any=null;
  for(let attempt=0;attempt<2;attempt++)try{
    const r=await fetch(url,{headers:{"User-Agent":"Mozilla/5.0 V2Microstructure/1.1"},signal:AbortSignal.timeout(12000)});
    if(r.status===404)return[];if(!r.ok)throw Error(`${symbol} ${d.toISOString()} ${r.status}`);
    const enc=new Uint8Array(await r.arrayBuffer());if(!enc.length)return[];
    const bytes=decode((LZMA as any).decompress(enc)),dv=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),m=new Map<number,any>();
    for(let o=0;o+20<=bytes.length;o+=20){
      const ofs=dv.getUint32(o,false),ask=dv.getUint32(o+4,false)/100000,bid=dv.getUint32(o+8,false)/100000,av=dv.getFloat32(o+12,false),bv=dv.getFloat32(o+16,false);
      if(!(ask>=bid&&bid>0&&ask-bid<.01))continue;
      const t=d.getTime()+ofs,k=Math.floor(t/60000)*60000;if(Date.now()<k+60000)continue;
      const sp=(ask-bid)/PIP,b=m.get(k);
      if(!b)m.set(k,{symbol,ts:new Date(k).toISOString(),bid_open:bid,bid_high:bid,bid_low:bid,bid_close:bid,ask_open:ask,ask_high:ask,ask_low:ask,ask_close:ask,spread_open_pips:sp,spread_high_pips:sp,spread_low_pips:sp,spread_close_pips:sp,spread_sum:sp,tick_count:1,ask_volume:Number.isFinite(av)?av:0,bid_volume:Number.isFinite(bv)?bv:0,source:SRC});
      else{b.bid_high=Math.max(b.bid_high,bid);b.bid_low=Math.min(b.bid_low,bid);b.bid_close=bid;b.ask_high=Math.max(b.ask_high,ask);b.ask_low=Math.min(b.ask_low,ask);b.ask_close=ask;b.spread_high_pips=Math.max(b.spread_high_pips,sp);b.spread_low_pips=Math.min(b.spread_low_pips,sp);b.spread_close_pips=sp;b.spread_sum+=sp;b.tick_count++;if(Number.isFinite(av))b.ask_volume+=av;if(Number.isFinite(bv))b.bid_volume+=bv}
    }
    return[...m.values()].map(b=>{const x={...b,spread_mean_pips:b.spread_sum/b.tick_count};delete x.spread_sum;return x as M});
  }catch(e){last=e;if(attempt===0)await new Promise(r=>setTimeout(r,250))}
  throw last??Error("hour failed");
}
async function pool<T,R>(xs:T[],n:number,f:(x:T)=>Promise<R>){const out:R[]=[];let i=0;async function w(){for(;;){const k=i++;if(k>=xs.length)return;out[k]=await f(xs[k])}}await Promise.all(Array.from({length:Math.min(n,xs.length)},()=>w()));return out}
async function save(rows:M[]){for(let i=0;i<rows.length;i+=200){const q=await db.from("fx_microstructure_1m").upsert(rows.slice(i,i+200),{onConflict:"symbol,ts,source"});if(q.error)throw Error(q.error.message)}}
Deno.serve(async()=>{try{
  const now=new Date();now.setUTCMinutes(0,0,0);const jobs:any[]=[];const plan:any={};
  for(const symbol of SYMBOLS){const q=await db.from("fx_microstructure_1m").select("ts").eq("symbol",symbol).order("ts",{ascending:false}).limit(1);if(q.error)throw Error(q.error.message);const last=q.data?.[0]?.ts?new Date(q.data[0].ts).getTime():0;const lagHours=last?Math.ceil((now.getTime()-last)/3600000):36,hours=Math.max(4,Math.min(36,lagHours+2));plan[symbol]={lastStored:q.data?.[0]?.ts??null,hours};for(let i=0;i<hours;i++)jobs.push({symbol,d:new Date(now.getTime()-i*3600000)})}
  const errors:string[]=[];const batches=await pool(jobs,2,async x=>{try{return await fetchHour(x.symbol,x.d)}catch(e){errors.push(`${x.symbol} ${x.d.toISOString()} ${String(e)}`);return[]}}),rows=batches.flat();await save(rows);
  const by:any={};for(const s of SYMBOLS){const z=rows.filter(x=>x.symbol===s).sort((a,b)=>Date.parse(a.ts)-Date.parse(b.ts));by[s]={minutes:z.length,newest:z.at(-1)?.ts??null,oldest:z[0]?.ts??null,meanSpreadPips:z.length?z.reduce((a,b)=>a+b.spread_mean_pips,0)/z.length:null,ticks:z.reduce((a,b)=>a+b.tick_count,0),plannedHours:plan[s].hours}}
  return J({ok:true,rows:rows.length,by,errors:errors.slice(0,10)});
}catch(e){console.error(e);return J({error:e instanceof Error?e.message:String(e)},500)}});