import { readFileSync } from 'node:fs';

const endpoint='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/trade-quality?symbol=EURUSD,GBPUSD';
const js=readFileSync('web/v31-quality.js','utf8');
const loader=readFileSync('web/v29-market-context.js','utf8');
const migration=readFileSync('supabase/migrations/20260813071500_v30_stop_breathing_room.sql','utf8');
for(const token of ['Setup quality','Why this grade?','fastAttention','breathing-room rule'])if(!js.includes(token))throw new Error(`v31 UI missing ${token}`);
for(const token of ['v31-quality.js','v31-quality.css'])if(!loader.includes(token))throw new Error(`v31 loader missing ${token}`);
for(const token of ["EURUSD' then 4.0","else 5.0","unchanged_1pct_at_entry","greatest(structural_risk, floor_distance)"])if(!migration.includes(token))throw new Error(`stop-floor migration missing ${token}`);
const r=await fetch(endpoint,{headers:{'cache-control':'no-cache'}});
if(!r.ok)throw new Error(`trade-quality HTTP ${r.status}`);
const d=await r.json();
if(d.version!=='V3.1 setup quality')throw new Error(`unexpected version ${d.version}`);
if(d.methodology?.automaticTradeChange!==false)throw new Error('quality layer must not mutate trades');
if(!d.current?.EURUSD||!d.current?.GBPUSD)throw new Error('both FX pairs must be returned');
if(!Number.isFinite(Number(d.winRate?.decisiveWinRatePct))||!Number.isFinite(Number(d.winRate?.scoredClosureWinSharePct)))throw new Error('win-rate denominators missing');
if('probability' in (d.current?.EURUSD?.quality||{})||'probability' in (d.current?.GBPUSD?.quality||{}))throw new Error('current quality must not expose a win probability');
if(!d.historicalInteractionEvidence?.directFirstInteraction||!d.historicalInteractionEvidence?.priorShallowTouch)throw new Error('historical interaction evidence missing');
console.log(JSON.stringify({version:d.version,winRate:d.winRate,current:Object.fromEntries(Object.entries(d.current).map(([k,v])=>[k,{quality:v.quality?.label,attention:v.fastAttention?.status,riskPips:v.risk?.pips,stopPolicy:v.risk?.stopPolicyVersion}]))},null,2));
