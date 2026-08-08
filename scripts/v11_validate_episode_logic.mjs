import assert from 'node:assert/strict';

const M15=15*60_000;
const iso=x=>new Date(x).toISOString();
const key=(s,d,t)=>`${s}:${d}:${iso(t)}`;
function build(rows){const out=[];let cur=null;const start=r=>({episode_key:key(r.symbol,r.direction,r.at),symbol:r.symbol,direction:r.direction,status:'active',started_at:iso(r.at),ended_at:null,max_stage:3});for(const r of rows){if(r.stage>=3&&r.direction){if(!cur)cur=start(r);else if(cur.direction!==r.direction){cur.status='ended';cur.ended_at=iso(r.at);out.push(cur);cur=start(r)}cur.max_stage=Math.max(cur.max_stage,r.stage)}else if(cur){cur.status='ended';cur.ended_at=iso(r.at);out.push(cur);cur=null}}if(cur)out.push(cur);return out}
const rows=[
 {symbol:'EURUSD',at:'2026-01-01T00:00:00Z',stage:0,direction:null},
 {symbol:'EURUSD',at:'2026-01-01T00:15:00Z',stage:3,direction:'long'},
 {symbol:'EURUSD',at:'2026-01-01T00:30:00Z',stage:4,direction:'long'},
 {symbol:'EURUSD',at:'2026-01-01T00:45:00Z',stage:6,direction:'long'},
 {symbol:'EURUSD',at:'2026-01-01T01:00:00Z',stage:3,direction:'short'},
 {symbol:'EURUSD',at:'2026-01-01T01:15:00Z',stage:4,direction:'short'},
 {symbol:'EURUSD',at:'2026-01-01T01:30:00Z',stage:0,direction:null},
];
const eps=build(rows);assert.equal(eps.length,2);assert.equal(eps[0].direction,'long');assert.equal(eps[0].max_stage,6);assert.equal(eps[0].status,'ended');assert.equal(eps[1].direction,'short');assert.equal(eps[1].max_stage,4);assert.equal(eps[1].status,'ended');assert.notEqual(eps[0].episode_key,eps[1].episode_key);

function closeAt(bars,anchorAt,minutes){const a=new Date(anchorAt).getTime(),target=a+minutes*60_000,x=bars.filter(b=>new Date(b.ts).getTime()>=a&&new Date(b.ts).getTime()+M15<=target);return x.at(-1)?.close??null}
const bars=[
 {ts:'2026-01-01T00:15:00Z',close:1.0010},{ts:'2026-01-01T00:30:00Z',close:1.0020},{ts:'2026-01-01T00:45:00Z',close:0.9990},{ts:'2026-01-01T01:00:00Z',close:1.0040},
];
assert.equal(closeAt(bars,'2026-01-01T00:15:00Z',15),1.0010);assert.equal(closeAt(bars,'2026-01-01T00:15:00Z',30),1.0020);assert.equal(closeAt(bars,'2026-01-01T00:15:00Z',60),1.0040);
const raw=(1.0040/1.0-1)*10000;assert.ok(Math.abs(raw-40)<1e-9);assert.equal(Math.sign(raw*1),1);assert.equal(Math.sign(raw*-1),-1);

const evidence=n=>n<10?'insufficient':n<30?'early':n<100?'building':'research-ready';assert.equal(evidence(0),'insufficient');assert.equal(evidence(9),'insufficient');assert.equal(evidence(10),'early');assert.equal(evidence(30),'building');assert.equal(evidence(100),'research-ready');
console.log('v1.1 episode logic validation passed: direction flips split episodes, horizons are event-time based, and evidence gates abstain below n=10');