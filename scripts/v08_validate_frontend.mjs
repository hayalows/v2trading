import fs from 'node:fs';
import vm from 'node:vm';

const html=fs.readFileSync('web/index.html','utf8');
const css=fs.readFileSync('web/v11.css','utf8');
const js=fs.readFileSync('web/v11.js','utf8');
const requiredHtml=['Version 1.1','Episode intelligence','Evidence gate','Prospective evidence','Data trust','v11.css','v11.js','aria-label="Primary navigation"','role="status"'];
for(const m of requiredHtml)if(!html.includes(m))throw new Error(`Missing v1.1 HTML marker: ${m}`);
const requiredCss=['min-height:48px',':focus-visible','prefers-reduced-motion','@media(min-width:720px)','@media(min-width:1000px)','.bottom','.rail'];
for(const m of requiredCss)if(!css.includes(m))throw new Error(`Missing v1.1 CSS/accessibility marker: ${m}`);
const requiredJs=['lab-insights','episode','evidence','safeToInterpret','favorable1hWilson95','s3.tradingview.com','Research intelligence refreshed'];
for(const m of requiredJs)if(!js.includes(m))throw new Error(`Missing v1.1 intelligence marker: ${m}`);
new vm.Script(js,{filename:'web/v11.js'});
if((css.match(/min-(?:width|height):48px/g)||[]).length<2)throw new Error('Expected explicit 48px interaction target rules');
if(!html.includes('Check evidence')||!html.includes('Open chart'))throw new Error('Primary investigation actions missing');
console.log('v1.1 frontend validation passed: syntax, mobile/expanded navigation, accessibility, TradingView and evidence gates present');