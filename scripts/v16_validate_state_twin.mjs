import fs from 'node:fs';
import vm from 'node:vm';

const html=fs.readFileSync('web/index.html','utf8');
const js=fs.readFileSync('web/v16-state-twin.js','utf8');
const css=fs.readFileSync('web/v16.css','utf8');
for(const marker of ['Version 1.6 · StateTwin','/v16.css','/v16-state-twin.js','focusBoard','evidenceView'])if(!html.includes(marker))throw new Error(`missing v1.6 HTML marker: ${marker}`);
for(const marker of ['StateTwin intelligence','Comparable states','Regime stability','Cross-pair structure','What changed','Outcome probability stays hidden','challenger models'])if(!js.toLowerCase().includes(marker.toLowerCase()))throw new Error(`missing StateTwin behavior: ${marker}`);
for(const marker of ['.stateTwinCard','.stateTwinGrid','.stateTwinChanges','@media(max-width:560px)'])if(!css.includes(marker))throw new Error(`missing StateTwin style: ${marker}`);
new vm.Script(js,{filename:'web/v16-state-twin.js'});
console.log('v1.6 StateTwin frontend validation passed: focus intelligence, explicit abstention, research disclosure and responsive styles present');
