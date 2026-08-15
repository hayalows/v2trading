const fs = require('fs');
const path = require('path');
const { getHistoricalRates } = require('dukascopy-node');

const instrument = String(process.argv[2] || '').toLowerCase();
const out = process.argv[3];
const from = process.argv[4] || '2005-01-01';
const to = process.argv[5] || '2025-12-31';
const supported = ['eurusd','gbpusd','audusd','nzdusd','usdjpy','usdchf','usdcad'];
if (!supported.includes(instrument)) throw new Error(`Unsupported: ${instrument}`);
if (!out) throw new Error('Output path required');

(async()=>{
  fs.mkdirSync(path.dirname(out),{recursive:true});
  const rows=await getHistoricalRates({
    instrument,
    dates:{from:new Date(`${from}T00:00:00Z`),to:new Date(`${to}T23:59:59Z`)},
    timeframe:'m15',format:'json',priceType:'bid',volumes:true,ignoreFlats:true,
    batchSize:80,pauseBetweenBatchesMs:20
  });
  if(!Array.isArray(rows)||rows.length<1000) throw new Error(`Unexpected ${instrument} rows: ${Array.isArray(rows)?rows.length:typeof rows}`);
  fs.writeFileSync(out,JSON.stringify(rows));
  console.log(JSON.stringify({instrument,rows:rows.length,first:rows[0],last:rows.at(-1)}));
})().catch(e=>{console.error(e);process.exit(1)});
