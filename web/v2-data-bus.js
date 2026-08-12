(()=>{
  const PAPER_BASE='https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/paper-trade-engine?symbol=EURUSD,GBPUSD';
  const cache={light:{value:null,at:0,promise:null},chart:{value:null,at:0,promise:null}};
  const ttl=15_000;
  async function load(kind='light',force=false){
    const slot=cache[kind],url=`${PAPER_BASE}&bars=${kind==='chart'?'1':'0'}`;
    if(!force&&slot.value&&Date.now()-slot.at<ttl)return slot.value;
    if(!force&&slot.promise)return slot.promise;
    slot.promise=fetch(url,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`paper snapshot ${r.status}`);return r.json()}).then(value=>{slot.value=value;slot.at=Date.now();return value}).finally(()=>{slot.promise=null});
    return slot.promise;
  }
  globalThis.__V2DataBus=globalThis.__V2DataBus||{paper:load};
})();
