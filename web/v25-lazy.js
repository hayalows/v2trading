(()=>{
  const SELF=document.currentScript?.src||'';
  const BASE=SELF&&SELF.includes('/')?SELF.slice(0,SELF.lastIndexOf('/')+1):'/';
  const pending=new Map();
  const styles=new Set();

  function addStyle(file,id=file){
    if(styles.has(id)||document.querySelector(`link[data-v25-lazy="${id}"]`)||document.querySelector(`link[href$="${file}"]`))return;
    const l=document.createElement('link');l.rel='stylesheet';l.href=BASE+file;l.dataset.v25Lazy=id;document.head.appendChild(l);styles.add(id);
  }
  function addScript(file,id=file,src=BASE+file){
    if(document.querySelector(`script[data-v25-lazy="${id}"]`)||document.querySelector(`script[src$="${file}"]`))return Promise.resolve();
    if(pending.has(id))return pending.get(id);
    const p=new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=src;s.dataset.v25Lazy=id;s.onload=()=>resolve();s.onerror=()=>reject(new Error(`Could not load ${file}`));document.body.appendChild(s)}).finally(()=>pending.delete(id));
    pending.set(id,p);return p;
  }

  async function loadTrades(){
    if(document.querySelector('script[src$="paper-trades.js"]'))return;
    try{
      if(!window.LightweightCharts)await addScript('lightweight-charts.standalone.production.js','lightweight-charts','https://cdn.jsdelivr.net/npm/lightweight-charts@5.2.0/dist/lightweight-charts.standalone.production.js');
      await addScript('paper-trades.js','paper-trades');
    }catch(e){console.warn('V2 trades lazy load',e);if(typeof snack==='function')snack('Trade details could not load')}
  }

  async function loadResearch(){
    if(document.querySelector('script[src$="v17-shadow.js"]'))return;
    try{
      addStyle('v16.css','v16-css');addStyle('v17.css','v17-css');
      await addScript('v16-state-twin.js','v16-js');
      await addScript('v17-shadow.js','v17-js');
    }catch(e){console.warn('V2 research lazy load',e);if(typeof snack==='function')snack('Research modules could not load')}
  }

  document.addEventListener('v2:view',e=>{
    const id=e.detail?.id;
    if(id==='tradesView')loadTrades();
    if(id==='evidenceView')loadResearch();
  });

  if(document.getElementById('tradesView')?.classList.contains('active'))loadTrades();
  if(document.getElementById('evidenceView')?.classList.contains('active'))loadResearch();
})();
