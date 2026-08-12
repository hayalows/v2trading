import {spawn,execFileSync} from 'node:child_process';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function chromePath(){
  for(const name of ['google-chrome','google-chrome-stable','chromium','chromium-browser']){
    try{return execFileSync('which',[name],{encoding:'utf8'}).trim()}catch{}
  }
  throw new Error('Chrome/Chromium not found on runner');
}
async function waitJson(url,timeout=12000){
  const end=Date.now()+timeout;
  while(Date.now()<end){
    try{const r=await fetch(url);if(r.ok)return await r.json()}catch{}
    await sleep(150);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

const root=process.cwd();
const server=spawn('python3',['-m','http.server','4173','--bind','127.0.0.1','--directory',root],{stdio:'ignore'});
const profile=mkdtempSync(join(tmpdir(),'v2-chrome-'));
const chrome=spawn(chromePath(),[
  '--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage',
  '--remote-debugging-port=9222',`--user-data-dir=${profile}`,'about:blank'
],{stdio:'ignore'});

let ws;
try{
  const version=await waitJson('http://127.0.0.1:9222/json/version');
  ws=new WebSocket(version.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
  let seq=0;const waiting=new Map();const exceptions=[];
  ws.addEventListener('message',e=>{
    const m=JSON.parse(e.data);
    if(m.id&&waiting.has(m.id)){const {resolve,reject}=waiting.get(m.id);waiting.delete(m.id);m.error?reject(new Error(m.error.message)):resolve(m.result);return}
    if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params?.exceptionDetails?.text||'Uncaught exception');
  });
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;waiting.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
  const evalJs=async expression=>{
    const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    if(r.exceptionDetails)throw new Error(r.exceptionDetails.text||'Runtime evaluation failed');
    return r.result?.value;
  };
  await call('Page.enable');await call('Runtime.enable');
  await call('Page.navigate',{url:'http://127.0.0.1:4173/web/index.html'});
  const end=Date.now()+12000;
  while(Date.now()<end){
    if(await evalJs("document.readyState==='complete' && typeof setView==='function'"))break;
    await sleep(100);
  }
  if(!await evalJs("document.readyState==='complete' && typeof setView==='function'"))throw new Error('Core navigation did not initialize');
  const expected=[['chartView','chartView'],['tradesView','tradesView'],['evidenceView','evidenceView'],['dataView','dataView'],['overview','overview']];
  for(const [button,view] of expected){
    const ok=await evalJs(`(()=>{const b=document.querySelector('[data-view="${button}"]');if(!b)return false;b.click();return true})()`);
    if(!ok)throw new Error(`Missing navigation button ${button}`);
    await sleep(180);
    const active=await evalJs("document.querySelector('.view.active')?.id||''");
    if(active!==view)throw new Error(`Click ${button} left active view as ${active||'none'}`);
  }
  const pairDeadline=Date.now()+15000;
  let pairs=0;
  while(Date.now()<pairDeadline){pairs=await evalJs("document.querySelectorAll('[data-pair]').length");if(pairs===2)break;await sleep(250)}
  if(pairs!==2)throw new Error(`Expected exactly 2 FX pair buttons, found ${pairs}`);
  const labels=await evalJs("[...document.querySelectorAll('[data-pair]')].map(x=>x.dataset.pair).join(',')");
  if(labels!=='EURUSD,GBPUSD')throw new Error(`Unexpected pair list: ${labels}`);
  if(exceptions.length)throw new Error(`Uncaught browser exception: ${exceptions.join(' | ')}`);
  console.log('browser smoke passed: FX shell navigates across all five views and exposes only EURUSD/GBPUSD');
} finally {
  try{ws?.close()}catch{}
  chrome.kill('SIGKILL');server.kill('SIGKILL');
  rmSync(profile,{recursive:true,force:true});
}
