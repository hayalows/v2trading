import fs from 'node:fs';
import vm from 'node:vm';

const html=fs.readFileSync('web/index.html','utf8');
const js=fs.readFileSync('web/v16-state-twin.js','utf8');
const css=fs.readFileSync('web/v16.css','utf8');
for(const marker of ['StateTwin','/v16.css','/v16-state-twin.js','focusBoard','evidenceView'])if(!html.includes(marker))throw new Error(`missing StateTwin HTML marker: ${marker}`);
for(const marker of ['StateTwin intelligence','Comparable states','Regime stability','Cross-pair structure','What changed','prospective shadow calibration','accepted research candidate','Live probability','challenger models'])if(!js.toLowerCase().includes(marker.toLowerCase()))throw new Error(`missing StateTwin behavior: ${marker}`);
for(const marker of ['.stateTwinCard','.stateTwinGrid','.stateTwinChanges','.stateTwinEvidenceGrid','@media(max-width:560px)'])if(!css.includes(marker))throw new Error(`missing StateTwin style: ${marker}`);
new vm.Script(js,{filename:'web/v16-state-twin.js'});
console.log('StateTwin frontend validation passed: live intelligence, explicit shadow-calibration abstention, frozen research evidence and responsive styles present');
