import fs from 'node:fs';

const html=fs.readFileSync('web/index.html','utf8');
const js=fs.readFileSync('web/v15-focus.js','utf8');
const css=fs.readFileSync('web/v15.css','utf8');
const requiredIds=['focusBoard','pairSwitch','priority','heroSym','headline','heroCopy','why','statusGrid','nextText','lastChange','poiWatchSlot','paperTradeSlot','episodeSlot','evidenceMini','metrics','trends','details','chartTitle','chartState','chart','paperStats','paperCurrent','researchChartLabel','researchChart','paperHistory','stats','inferenceGate','evidenceCards','timeline','trust','refresh','marketDot','marketText','snack'];
for(const id of requiredIds){if(!html.includes(`id="${id}"`))throw new Error(`missing required id ${id}`)}
for(const asset of ['/v15.css','/v15-focus.js'])if(!html.includes(asset))throw new Error(`missing asset ${asset}`);
for(const label of ['Know what matters now.','Research details','Focus','Paper trades'])if(!html.includes(label))throw new Error(`missing focus copy: ${label}`);
for(const phrase of ['WAIT FOR POI','What must happen next','Historical revisit context','not a forecast for this trade','Conditional POI revisit research','AUC was <strong>0.627</strong>','not a current-trade probability'])if(!js.includes(phrase))throw new Error(`missing focus/research behavior: ${phrase}`);
for(const cls of ['.focusHero','.focusGrid','.researchDisclosure','@media(max-width:560px)'])if(!css.includes(cls))throw new Error(`missing responsive style ${cls}`);
if(!js.includes("GBPUSD:[{b:8,h:2,r:.3409}"))throw new Error('GBPUSD exact-live revisit curve missing');
if(!html.includes('Historical lifecycle base rates') && !js.includes('historical lifecycle base rate'))throw new Error('base-rate semantics missing');
console.log('v1.5 focus-mode frontend validation passed');
