const fs = require('fs');
const path = require('path');
const { getHistoricalRates } = require('dukascopy-node');

(async () => {
  const instrument = String(process.argv[2] || '').toLowerCase();
  const out = process.argv[3];
  const from = process.argv[4] || '2020-01-01';
  const to = process.argv[5] || new Date().toISOString().slice(0, 10);
  if (!['eurusd','gbpusd','xauusd'].includes(instrument)) throw new Error(`Unsupported instrument: ${instrument}`);
  if (!out) throw new Error('Output path is required');
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const rows = await getHistoricalRates({
    instrument,
    dates: { from: new Date(`${from}T00:00:00Z`), to: new Date(`${to}T23:59:59Z`) },
    timeframe: 'm15',
    format: 'json',
    priceType: 'bid',
    volumes: true,
    ignoreFlats: false,
    batchSize: 20,
    pauseBetweenBatchesMs: 120
  });
  if (!Array.isArray(rows) || rows.length < 1000) throw new Error(`Unexpected ${instrument} history rows: ${Array.isArray(rows) ? rows.length : typeof rows}`);
  fs.writeFileSync(out, JSON.stringify(rows));
  console.log(JSON.stringify({ instrument, rows: rows.length, first: rows[0], last: rows.at(-1), from, to }, null, 2));
})().catch(err => { console.error(err); process.exit(1); });
