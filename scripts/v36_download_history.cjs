const fs = require('fs');
const path = require('path');
const { getHistoricalRates } = require('dukascopy-node');

const instrument = String(process.argv[2] || '').toLowerCase();
const timeframe = String(process.argv[3] || 'm15').toLowerCase();
const out = process.argv[4];
const from = process.argv[5] || '2005-01-01';
const to = process.argv[6] || '2025-12-31';

if (!['eurusd','gbpusd'].includes(instrument)) throw new Error(`Unsupported instrument: ${instrument}`);
if (!['m5','m15'].includes(timeframe)) throw new Error(`Unsupported timeframe: ${timeframe}`);
if (!out) throw new Error('Output path required');

(async () => {
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const rows = await getHistoricalRates({
    instrument,
    dates: { from: new Date(`${from}T00:00:00Z`), to: new Date(`${to}T23:59:59Z`) },
    timeframe,
    format: 'json',
    priceType: 'bid',
    volumes: true,
    ignoreFlats: true,
    batchSize: 80,
    pauseBetweenBatchesMs: 20
  });
  if (!Array.isArray(rows) || rows.length < 1000) throw new Error(`Unexpected ${instrument} ${timeframe} rows: ${Array.isArray(rows) ? rows.length : typeof rows}`);
  fs.writeFileSync(out, JSON.stringify(rows));
  console.log(JSON.stringify({instrument,timeframe,rows:rows.length,first:rows[0],last:rows.at(-1),from,to}, null, 2));
})().catch(err => { console.error(err); process.exit(1); });
