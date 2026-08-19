import { DurableObject } from 'cloudflare:workers';

type Plan={trade_key:string;symbol:'EURUSD'|'GBPUSD';direction:'long'|'short';status:'armed'|'open';armed_at:string;entry_at:string|null;entry_price:number;stop_price:number;target_price:number};
type Quote={provider:string;symbol:'EURUSD'|'GBPUSD';observedAt:string;bid:number;ask:number;quoteId:string;meta:Record<string,unknown>};
type Env={
  FEED:DurableObjectNamespace<FeedGateway>;
  CTRADER_ENV:string;
  CTRADER_CLIENT_ID:string;
  CTRADER_CLIENT_SECRET:string;
  CTRADER_ACCESS_TOKEN:string;
  V2_FEED_INGEST_TOKEN:string;
  SUPABASE_GATEWAY_URL:string;
  SUPABASE_BRIDGE_URL:string;
};

const PT={HEARTBEAT:51,APP_AUTH_REQ:2100,APP_AUTH_RES:2101,ACCOUNT_AUTH_REQ:2102,ACCOUNT_AUTH_RES:2103,SYMBOLS_LIST_REQ:2114,SYMBOLS_LIST_RES:2115,SUB_SPOTS_REQ:2127,SUB_SPOTS_RES:2128,SPOT_EVENT:2131,ACCOUNTS_REQ:2149,ACCOUNTS_RES:2150,ERROR:50};
const SYMBOLS=['EURUSD','GBPUSD'] as const;
const norm=(x:any)=>String(x??'').toUpperCase().replace(/[^A-Z]/g,'');
const num=(x:any)=>Number.isFinite(Number(x))?Number(x):null;
const iso=(x:any)=>{const v=num(x);if(v==null)return new Date().toISOString();const ms=v>1e12?v:v*1000;const d=new Date(ms);return Number.isNaN(d.valueOf())?new Date().toISOString():d.toISOString()};
const msg=(payloadType:number,payload:any={})=>JSON.stringify({clientMsgId:crypto.randomUUID(),payloadType,payload});

export class FeedGateway extends DurableObject<Env>{
  private ws:WebSocket|null=null;
  private accountId:string|null=null;
  private symbols=new Map<string,'EURUSD'|'GBPUSD'>();
  private quoteSides=new Map<'EURUSD'|'GBPUSD',{bid:number|null;ask:number|null;ts:string}>();
  private latest=new Map<'EURUSD'|'GBPUSD',Quote>();
  private plans:Plan[]=[];
  private planFetchedAt=0;
  private lastSnapshotAt=0;
  private lastMessageAt=0;
  private lastConnectedAt=0;
  private state='standby';
  private error:string|null=null;
  private heartbeatTimer:number|null=null;
  private reconnecting=false;

  constructor(ctx:DurableObjectState,env:Env){super(ctx,env);}

  async fetch(req:Request){
    const u=new URL(req.url);
    if(u.pathname==='/status')return Response.json(this.safeStatus());
    if(u.pathname==='/ensure'){await this.ensure();return Response.json(this.safeStatus());}
    return new Response('not found',{status:404});
  }

  async alarm(){await this.ensure();await this.ctx.storage.setAlarm(Date.now()+5*60_000);}

  private safeStatus(){
    const missing=['CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN','V2_FEED_INGEST_TOKEN'].filter(k=>!String((this.env as any)[k]??'').trim());
    return{ok:missing.length===0,state:this.state,error:this.error,environment:this.env.CTRADER_ENV||'demo',missingSecrets:missing,connectedAt:this.lastConnectedAt?new Date(this.lastConnectedAt).toISOString():null,lastMessageAt:this.lastMessageAt?new Date(this.lastMessageAt).toISOString():null,accountId:this.accountId?'configured':null,symbols:[...this.symbols.values()],activePlans:this.plans.map(x=>({symbol:x.symbol,status:x.status,direction:x.direction,tradeKey:x.trade_key}))};
  }

  private async ensure(){
    await this.ctx.storage.setAlarm(Date.now()+5*60_000);
    const missing=this.safeStatus().missingSecrets;
    if(missing.length){this.state='setup_required';this.error=`Missing ${missing.join(', ')}`;return;}
    if(this.ws&&this.ws.readyState===WebSocket.OPEN)return;
    if(this.reconnecting)return;
    this.reconnecting=true;
    try{await this.connect()}finally{this.reconnecting=false;}
  }

  private async connect(){
    this.closeSocket();
    const demo=String(this.env.CTRADER_ENV||'demo').toLowerCase()!=='live';
    const host=demo?'demo.ctraderapi.com':'live.ctraderapi.com';
    this.state='connecting';this.error=null;
    const ws=new WebSocket(`wss://${host}:5036`);
    this.ws=ws;
    ws.addEventListener('open',()=>{this.state='authenticating';this.lastConnectedAt=Date.now();this.lastMessageAt=Date.now();this.send(PT.APP_AUTH_REQ,{clientId:this.env.CTRADER_CLIENT_ID,clientSecret:this.env.CTRADER_CLIENT_SECRET});this.startHeartbeat();});
    ws.addEventListener('message',(e)=>void this.onMessage(e));
    ws.addEventListener('error',()=>{this.state='error';this.error='cTrader WebSocket error';});
    ws.addEventListener('close',(e)=>{this.state='disconnected';this.error=`cTrader closed ${e.code}${e.reason?` · ${e.reason}`:''}`;this.closeSocket(false);void this.ctx.storage.setAlarm(Date.now()+15_000);});
  }

  private closeSocket(close=true){if(this.heartbeatTimer!=null){clearInterval(this.heartbeatTimer);this.heartbeatTimer=null;}if(close&&this.ws){try{this.ws.close(1000,'reconnect')}catch{}}this.ws=null;this.accountId=null;this.symbols.clear();}
  private startHeartbeat(){if(this.heartbeatTimer!=null)clearInterval(this.heartbeatTimer);this.heartbeatTimer=setInterval(()=>{if(this.ws?.readyState===WebSocket.OPEN)this.send(PT.HEARTBEAT,{})},10_000) as unknown as number;}
  private send(payloadType:number,payload:any){if(this.ws?.readyState===WebSocket.OPEN)this.ws.send(msg(payloadType,payload));}

  private async onMessage(e:MessageEvent){
    this.lastMessageAt=Date.now();
    let m:any;try{m=JSON.parse(typeof e.data==='string'?e.data:new TextDecoder().decode(e.data));}catch{return;}
    const p=m?.payload??{};
    if(m?.payloadType===PT.ERROR){this.state='error';this.error=`${p.errorCode||'cTrader error'}${p.description?` · ${p.description}`:''}`;return;}
    if(m?.payloadType===PT.APP_AUTH_RES){this.state='account_lookup';this.send(PT.ACCOUNTS_REQ,{accessToken:this.env.CTRADER_ACCESS_TOKEN});return;}
    if(m?.payloadType===PT.ACCOUNTS_RES){
      const demo=String(this.env.CTRADER_ENV||'demo').toLowerCase()!=='live';
      const accounts=(p.ctidTraderAccount??[]) as any[];
      const a=accounts.find(x=>Boolean(x.isLive)!==demo)||accounts[0];
      if(!a?.ctidTraderAccountId){this.state='error';this.error='No cTrader account available for selected environment';return;}
      this.accountId=String(a.ctidTraderAccountId);this.state='account_auth';this.send(PT.ACCOUNT_AUTH_REQ,{ctidTraderAccountId:this.accountId,accessToken:this.env.CTRADER_ACCESS_TOKEN});return;
    }
    if(m?.payloadType===PT.ACCOUNT_AUTH_RES){this.state='symbols';this.send(PT.SYMBOLS_LIST_REQ,{ctidTraderAccountId:this.accountId,includeArchivedSymbols:false});return;}
    if(m?.payloadType===PT.SYMBOLS_LIST_RES){
      const found:number[]=[];
      for(const s of (p.symbol??[]) as any[]){const n=norm(s.symbolName);if((SYMBOLS as readonly string[]).includes(n)){this.symbols.set(String(s.symbolId),n as any);found.push(Number(s.symbolId));}}
      if(found.length!==2){this.state='error';this.error=`Required symbols unavailable: found ${[...this.symbols.values()].join(', ')||'none'}`;return;}
      this.state='subscribing';this.send(PT.SUB_SPOTS_REQ,{ctidTraderAccountId:this.accountId,symbolId:found,subscribeToSpotTimestamp:true});return;
    }
    if(m?.payloadType===PT.SUB_SPOTS_RES){this.state='live';this.error=null;await this.refreshPlans(true);return;}
    if(m?.payloadType===PT.SPOT_EVENT)await this.onSpot(p);
  }

  private async onSpot(p:any){
    const symbol=this.symbols.get(String(p.symbolId));if(!symbol)return;
    const prev=this.quoteSides.get(symbol)??{bid:null,ask:null,ts:new Date().toISOString()};
    const b=num(p.bid),a=num(p.ask);if(b!=null)prev.bid=b/100000;if(a!=null)prev.ask=a/100000;prev.ts=iso(p.timestamp);this.quoteSides.set(symbol,prev);
    if(prev.bid==null||prev.ask==null||prev.ask<prev.bid)return;
    const q:Quote={provider:'cTrader Open API',symbol,observedAt:prev.ts,bid:prev.bid,ask:prev.ask,quoteId:`ctrader:${p.symbolId}:${p.timestamp??Date.now()}`,meta:{environment:this.env.CTRADER_ENV||'demo',stream:'ProtoOASpotEvent',brokerSpecific:true}};
    this.latest.set(symbol,q);
    if(Date.now()-this.planFetchedAt>5000)await this.refreshPlans();
    const plan=this.plans.find(x=>x.symbol===symbol);
    if(plan&&this.crossed(plan,q))await this.push([q],true);
    if(Date.now()-this.lastSnapshotAt>=10_000&&this.latest.size){this.lastSnapshotAt=Date.now();await this.push([...this.latest.values()],false);}
  }

  private crossed(t:Plan,q:Quote){
    if(t.status==='armed')return t.direction==='long'?q.ask<=Number(t.entry_price):q.bid>=Number(t.entry_price);
    if(t.status==='open')return t.direction==='long'?(q.bid<=Number(t.stop_price)||q.bid>=Number(t.target_price)):(q.ask>=Number(t.stop_price)||q.ask<=Number(t.target_price));
    return false;
  }

  private async refreshPlans(force=false){
    if(!force&&Date.now()-this.planFetchedAt<5000)return;
    this.planFetchedAt=Date.now();
    try{const r=await fetch(this.env.SUPABASE_GATEWAY_URL,{headers:{Accept:'application/json'},cf:{cacheTtl:0}} as any);if(!r.ok)throw new Error(`plan HTTP ${r.status}`);const j:any=await r.json();this.plans=Array.isArray(j.activePlans)?j.activePlans:[];}catch(e){this.error=`plan refresh: ${String(e)}`;}
  }

  private async push(quotes:Quote[],crossing:boolean){
    if(!quotes.length)return;
    try{
      const r=await fetch(this.env.SUPABASE_BRIDGE_URL,{method:'POST',headers:{'Content-Type':'application/json','x-v2-feed-token':this.env.V2_FEED_INGEST_TOKEN},body:JSON.stringify({quotes})});
      if(!r.ok)throw new Error(`bridge HTTP ${r.status}`);
      const j:any=await r.json();
      if(crossing&&Array.isArray(j.results)){
        for(const x of j.results){if(x?.tradeKey&&x?.applied&&x?.action==='stream_entry'){const p=this.plans.find(y=>y.trade_key===x.tradeKey);if(p){p.status='open';p.entry_at=quotes.find(q=>q.symbol===p.symbol)?.observedAt??new Date().toISOString();}}if(x?.tradeKey&&x?.applied&&['stream_win','stream_loss'].includes(x?.action))this.plans=this.plans.filter(y=>y.trade_key!==x.tradeKey);}
      }
    }catch(e){this.error=`bridge: ${String(e)}`;}
  }
}

export default {
  async fetch(req:Request,env:Env){const u=new URL(req.url);const stub=env.FEED.getByName(`ctrader-${env.CTRADER_ENV||'demo'}`);if(u.pathname==='/status')return stub.fetch(new Request('https://feed/status'));if(u.pathname==='/ensure'&&req.method==='POST')return stub.fetch(new Request('https://feed/ensure',{method:'POST'}));return Response.json({ok:true,service:'V2 live feed gateway',statusPath:'/status'});},
  async scheduled(_controller:ScheduledController,env:Env,ctx:ExecutionContext){const stub=env.FEED.getByName(`ctrader-${env.CTRADER_ENV||'demo'}`);ctx.waitUntil(stub.fetch(new Request('https://feed/ensure',{method:'POST'})).then(()=>undefined));}
};
