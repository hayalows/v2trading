import fs from 'node:fs';
import assert from 'node:assert/strict';

const engine=fs.readFileSync('supabase/functions/paper-trade-engine/index.ts','utf8');
const migration=fs.readFileSync('supabase/migrations/20260811_v20_poi_lifecycle_learning.sql','utf8');
const ui=fs.readFileSync('web/v20-poi-learning.js','utf8');
const loader=fs.readFileSync('web/v17-shadow.js','utf8');
const report=fs.readFileSync('reports/v20/V20_POI_LIFECYCLE_LEARNING.md','utf8');

for(const marker of [
  'V2 paper-trade engine v2.0',
  'DEPTH_PCTS = Array.from({ length: 21 }, (_, i) => i * 5)',
  'PENETRATION_THRESHOLDS = [0, 10, 20, 30, 40, 45, 50, 65, 85, 100]',
  'PRICE_EPS = 1e-9',
  'SHADOW_ENTRY_HORIZON_BARS = 192',
  'baselineDepthPct: 50',
  'productionRuleChanged: false',
  'automaticPromotion: false',
  'backfillExcludedFromPromotion: true',
  'superseded_by_newer_same_direction_plan',
  'invalidated_close_through',
  'poi_penetration_events',
  'poi_depth_shadow'
]) assert.ok(engine.includes(marker),`missing v2.0 engine boundary: ${marker}`);

assert.match(engine,/const entry = \(low \+ high\) \/ 2/,'baseline paper entry must remain midpoint');
assert.match(engine,/REWARD_R\s*=\s*2\.5/,'2.5R target must remain frozen');
assert.match(engine,/MIN_RISK_ATR\s*=\s*0\.08/);
assert.match(engine,/MAX_RISK_ATR\s*=\s*1\.60/);
assert.ok(!engine.includes('bestDepthSignal'),'no live best-depth signal may exist');
assert.ok(!engine.includes('promoteDepthAutomatically'),'no automatic depth promotion may exist');

for(const marker of [
  'max_poi_penetration','poi_lifecycle_state','focus_active','focus_suppression_reason','superseded_by_trade_key',
  'create table if not exists public.poi_depth_shadow','create table if not exists public.poi_penetration_events',
  'prospective boolean not null','not_filled','enable row level security','revoke all on public.poi_depth_shadow from anon, authenticated'
]) assert.ok(migration.includes(marker),`missing v2.0 schema boundary: ${marker}`);

for(const state of ['untouched','grazed','partially_mitigated','midpoint_touched','deep_unfilled','distal_touched','invalidated_close_through']) assert.ok(migration.includes(`'${state}'`),`missing lifecycle state ${state}`);

for(const marker of ['50% stays baseline','Alternatives learn in shadow','Backfilled observations never count toward promotion','No automatic promotion','Research watch','Max penetration']) assert.ok(ui.includes(marker),`missing v2.0 UI boundary: ${marker}`);
for(const marker of ['/v20.css','/v20-poi-learning.js','data-v20-poi']) assert.ok(loader.includes(marker),`v2.0 additive loader missing ${marker}`);
for(const marker of ['KEEP_MIDPOINT_RESEARCH_ONLY','40%','walk-forward','prospective','backfilled','no broker']) assert.ok(report.toLowerCase().includes(marker.toLowerCase()),`v2.0 report missing ${marker}`);

console.log('v2.0 POI learning validation passed: midpoint baseline frozen, lifecycle semantics explicit, backfill separated and depth shadows have zero automatic product influence');
