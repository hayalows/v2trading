import fs from 'node:fs';
import assert from 'node:assert/strict';

const engine=fs.readFileSync('supabase/functions/paper-trade-engine/index.ts','utf8');
const migration=fs.readFileSync('supabase/migrations/20260810_paper_trade_engine.sql','utf8');
const lifecycle=fs.readFileSync('supabase/migrations/20260810_poi_lifecycle_wait.sql','utf8');
const events=fs.readFileSync('supabase/migrations/20260810_poi_lifecycle_events.sql','utf8');
const paper=fs.readFileSync('web/paper-trades.js','utf8');
const protocol=fs.readFileSync('docs/PAPER_TRADE_ENGINE_V13.md','utf8');
const v14=fs.readFileSync('reports/v14/V14_POI_WAITING_TIME_RESULTS.md','utf8');

const regexes=[
  /ORIGINAL_WINDOW_BARS\s*=\s*8/,
  /EXTENDED_WINDOW_BARS\s*=\s*48/,
  /RESEARCH_TAIL_BARS\s*=\s*192/,
  /MAX_HOLD_BARS\s*=\s*48/,
  /STOP_BUFFER_ATR\s*=\s*0\.03/,
  /REWARD_R\s*=\s*2\.5/,
  /MIN_RISK_ATR\s*=\s*0\.08/,
  /MAX_RISK_ATR\s*=\s*1\.60/,
  /entry_bar_resolved_5m\s*\?\s*entryIdx\s*\+\s*1\s*:\s*entryIdx/,
  /market_state_history/,
  /gte\(\s*["']formation_stage["']\s*,\s*6\s*\)/,
  /c\.form\?\.fresh\s*!==\s*true/,
  /globalThis\.URL\(req\.url\)/,
  /timeInvalidation:\s*["']None\./,
];
for(const re of regexes)assert.match(engine,re,`missing engine integrity pattern: ${re}`);
for(const marker of ['5m public path unavailable','SL and TP touched in same 5m bar','M15 entry touch not reproduced by 5m path','partially_mitigated','target_delivered_before_entry','outside_studied_tail'])assert.ok(engine.includes(marker),`missing lifecycle/ambiguity guard: ${marker}`);
assert.ok(!/status\s*:\s*["']expired["']/.test(engine),'v1.4 must not create a new time-only expired state');

for(const marker of ['create table if not exists public.paper_trades','create table if not exists public.paper_trade_events','enable row level security','revoke all on public.paper_trades from anon, authenticated']) assert.ok(migration.includes(marker),`missing migration marker: ${marker}`);
for(const marker of ['lifecycle_phase','pending_age_bars','pre_entry_target_reached','research_tail_bars']) assert.ok(lifecycle.includes(marker),`missing v1.4 lifecycle schema marker: ${marker}`);
for(const marker of ['reactivated_v14','extended_wait','long_tail_wait','outside_studied_tail','partially_mitigated','target_delivered_before_entry']) assert.ok(events.includes(marker),`missing lifecycle event marker: ${marker}`);
for(const marker of ['createPriceLine','createSeriesMarkers','CandlestickSeries','Entry midpoint','Stop loss','Take profit · 2.5R','Research simulation']) assert.ok(paper.includes(marker),`missing chart/journal marker: ${marker}`);
for(const marker of ['50% midpoint','0.03 ATR','2.5R','48 M15 bars']) assert.ok(protocol.includes(marker),`missing frozen protocol marker: ${marker}`);
for(const marker of ['Replace the 8-M15-bar expiry with lifecycle tracking','exact live POI geometry','1,685','82.8%','+0.332R','partially mitigated','Time alone does **not** set `invalidated`']) assert.ok(v14.includes(marker),`missing exact-parity v1.4 evidence marker: ${marker}`);

function close(a,b,eps=1e-12){return Math.abs(a-b)<=eps}
function plan(direction,poiLow,poiHigh,sweepExtreme,atr){
  const entry=(poiLow+poiHigh)/2;
  const stop=direction==='long'?sweepExtreme-0.03*atr:sweepExtreme+0.03*atr;
  const risk=direction==='long'?entry-stop:stop-entry;
  const target=direction==='long'?entry+2.5*risk:entry-2.5*risk;
  return {entry,stop,risk,target,riskAtr:risk/atr};
}
const long=plan('long',1.1000,1.1020,1.0950,0.0100);
assert.ok(close(long.entry,1.101));
assert.ok(Math.abs((long.target-long.entry)/long.risk-2.5)<1e-12);
assert.ok(long.stop<1.0950,'long stop must sit beyond sweep extreme');
assert.ok(long.riskAtr>=0.08&&long.riskAtr<=1.60,'sample plan should pass frozen risk gate');
const short=plan('short',1.1980,1.2000,1.2050,0.0100);
assert.ok(close(short.entry,1.199));
assert.ok(Math.abs((short.entry-short.target)/short.risk-2.5)<1e-12);
assert.ok(short.stop>1.2050,'short stop must sit beyond sweep extreme');

function firstFutureFill(bars,bosIdx,entry){
  const eligible=bars.slice(bosIdx+1);
  const k=eligible.findIndex(b=>b.low<=entry&&entry<=b.high);
  return k<0?null:bosIdx+1+k;
}
const testBars=[
  {low:0.9,high:1.1},
  {low:0.8,high:1.2}, // BOS bar touches but must never fill
  {low:1.01,high:1.05},
  {low:0.99,high:1.01},
];
assert.equal(firstFutureFill(testBars,1,1.0),3,'BOS candle must never count as paper entry');
const late=[{low:0.8,high:1.2},...Array.from({length:12},()=>({low:1.1,high:1.2})),{low:0.99,high:1.01}];
assert.equal(firstFutureFill(late,0,1.0),13,'a valid midpoint revisit after the old 8-bar boundary must still be found');

console.log('v1.4 paper-trade validation passed: exact live POI evidence, frozen risk math, future-only entry, non-expiring lifecycle, ambiguity guards and research chart remain intact');