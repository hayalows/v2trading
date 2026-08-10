import assert from 'node:assert/strict';

function buildCampaigns(rows){
  const out=[];let cur=null;
  for(const r of rows){
    if(r.stage>=3&&r.direction){
      if(!cur||cur.direction!==r.direction){
        if(cur){cur.status='ended';cur.endedAt=r.at;out.push(cur)}
        cur={direction:r.direction,status:'active',startedAt:r.at,maxStage:r.stage,sweeps:new Set(r.sweep?[r.sweep]:[])};
      }else{
        cur.maxStage=Math.max(cur.maxStage,r.stage);
        if(r.sweep)cur.sweeps.add(r.sweep);
      }
    }else if(cur){cur.status='ended';cur.endedAt=r.at;out.push(cur);cur=null}
  }
  if(cur)out.push(cur);
  return out.map(c=>({...c,sweepCount:c.sweeps.size}));
}

const rows=[
  {at:'2026-08-10T07:25:00Z',stage:3,direction:'short',sweep:'2026-08-10T07:00:00Z'},
  {at:'2026-08-10T07:40:00Z',stage:4,direction:'short',sweep:'2026-08-10T07:00:00Z'},
  {at:'2026-08-10T08:10:00Z',stage:3,direction:'short',sweep:'2026-08-10T07:45:00Z'},
  {at:'2026-08-10T08:40:00Z',stage:3,direction:'short',sweep:'2026-08-10T08:15:00Z'},
  {at:'2026-08-10T09:40:00Z',stage:3,direction:'short',sweep:'2026-08-10T09:15:00Z'},
  {at:'2026-08-10T09:55:00Z',stage:4,direction:'short',sweep:'2026-08-10T09:15:00Z'},
  {at:'2026-08-10T11:00:00Z',stage:0,direction:null,sweep:null},
];
const campaigns=buildCampaigns(rows);
assert.equal(campaigns.length,1,'repeated same-direction sweeps must remain one continuous campaign');
assert.equal(campaigns[0].sweepCount,4,'all distinct sweep events must be retained');
assert.equal(campaigns[0].maxStage,4);

const flip=buildCampaigns([
  {at:'2026-08-10T01:00:00Z',stage:3,direction:'long',sweep:'2026-08-10T00:45:00Z'},
  {at:'2026-08-10T02:00:00Z',stage:4,direction:'long',sweep:'2026-08-10T00:45:00Z'},
  {at:'2026-08-10T03:00:00Z',stage:3,direction:'short',sweep:'2026-08-10T02:45:00Z'},
]);
assert.equal(flip.length,2,'direction flip must start a new campaign');
assert.equal(flip[0].direction,'long');assert.equal(flip[1].direction,'short');

function independentEvidence(campaigns,episodeOutcomes){
  const selected=[];
  for(const c of campaigns){
    const xs=episodeOutcomes.filter(x=>x.campaign===c).sort((a,b)=>a.t-b.t);
    if(xs.length)selected.push(xs[0]);
  }
  return {raw:episodeOutcomes.length,independent:selected.length};
}
const c1={},c2={};
const ev=independentEvidence([c1,c2],[
  {campaign:c1,t:1},{campaign:c1,t:2},{campaign:c1,t:3},{campaign:c1,t:4},
  {campaign:c2,t:5},{campaign:c2,t:6},
]);
assert.equal(ev.raw,6);assert.equal(ev.independent,2,'six correlated sweep outcomes must collapse to two campaign observations');
const gate=n=>n>=10;assert.equal(gate(6),false);assert.equal(gate(9),false);assert.equal(gate(10),true);
console.log('v1.2 campaign logic validation passed: repeated sweeps stay inside one campaign and inference uses one outcome per campaign');
