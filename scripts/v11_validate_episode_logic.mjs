import assert from 'node:assert/strict';

const M15=15*60_000,iso=x=>new Date(x).toISOString();
const key=(s,d,sweep,at)=>`${s}:${d}:${iso(sweep||at)}`;
function build(rows){const out=[];let cur=null;const start=r=>({episode_key:key(r.symbol,r.direction,r.sweep,r.at),symbol:r.symbol,direction:r.direction,sweep:r.sweep,status:'active',started_at:iso(r.at),ended_at:null,end_reason:null,max_stage:3});for(const r of rows){if(r.stage>=3&&r.direction){if(!cur)cur=start(r);else if(cur.direction!==r.direction||(cur.sweep&&r.sweep&&cur.sweep!==r.sweep)){cur.status='ended';cur.ended_at=iso(r.at);cur.end_reason=cur.direction!==r.direction?'direction_flip':'new_sweep';out.push(cur);cur=start(r)}cur.max_stage=Math.max(cur.max_stage,r.stage)}else if(cur){cur.status='ended';cur.ended_at=iso(r.at);cur.end_reason='formation_reset';out.push(cur);cur=null}}if(cur)out.push(cur);return out}
const rows=[
 {symbol:'EURUSD',at:'2026-01-01T00:00:00Z',stage:0,direction:null,sweep:null},
 {symbol:'EURUSD',at:'2026-01-01T00:15:00Z',stage:3,direction:'long',sweep:'2026-01-01T00:00:00Z'},
 {symbol:'EURUSD',at:'2026-01-01T00:30:00Z',stage:6,direction:'long',sweep:'2026-01-01T00:00:00Z'},
 {symbol:'EURUSD',at:'2026-01-01T00:45:00Z',stage:3,direction:'long',sweep:'2026-01-01T00:30:00Z'},
 {symbol:'EURUSD',at:'2026-01-01T01:00:00Z',stage:4,direction:'long',sweep:'2026-01-01T00:30:00Z'},
 {symbol:'EURUSD',at:'2026-01-01T01:15:00Z',stage:3,direction:'short',sweep:'2026-01-01T01:00:00Z'},
 {symbol:'EURUSD',at:'2026-01-01T01:30:00Z',stage:0,direction:null,sweep:null},
];
const eps=build(rows);assert.equal(eps.length,3);assert.equal(eps[0].direction,'long');assert.equal(eps[0].max_stage,6);assert.equal(eps[0].end_reason,'new_sweep');assert.equal(eps[1].direction,'long');assert.equal(eps[1].max_stage,4);assert.equal(eps[1].end_reason,'direction_flip');assert.equal(eps[2].direction,'short');assert.equal(eps[2].end_reason,'formation_reset');assert.notEqual(eps[0].episode_key,eps[1].episode_key);

function closeAt(bars,anchorAt,minutes){const a=new Date(anchorAt).getTime(),target=a+minutes*60_000,x=bars.filter(b=>new Date(b.ts).getTime()>=a&&new Date(b.ts).getTime()+M15<=target);return x.at(-1)?.close??null}
const bars=[{ts:'2026-01-01T00:15:00Z',close:1.001},{ts:'2026-01-01T00:30:00Z',close:1.002},{ts:'2026-01-01T00:45:00Z',close:.999},{ts:'2026-01-01T01:00:00Z',close:1.004}];
assert.equal(closeAt(bars,'2026-01-01T00:15:00Z',15),1.001);assert.equal(closeAt(bars,'2026-01-01T00:15:00Z',30),1.002);assert.equal(closeAt(bars,'2026-01-01T00:15:00Z',60),1.004);const raw=(1.004/1-1)*10000;assert.ok(Math.abs(raw-40)<1e-9);assert.equal(Math.sign(raw),1);assert.equal(Math.sign(-raw),-1);
const evidence=n=>n<10?'insufficient':n<30?'early':n<100?'building':'research-ready';assert.equal(evidence(9),'insufficient');assert.equal(evidence(10),'early');assert.equal(evidence(30),'building');assert.equal(evidence(100),'research-ready');
console.log('v1.1 episode logic validation passed: new sweeps and direction flips split episodes, horizons are event-time based, and evidence gates abstain below n=10');