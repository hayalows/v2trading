const fs = require('fs');
const path = require('path');
const { getHistoricalRates } = require('dukascopy-node');

(async () => {
  const out = process.argv[2] || '.research-data/xauusd-m15.json';
  const from = process.argv[3] || '2020-01-01';
  const to = process.argv[4] || new Date().toISOString().slice(0, 10);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const rows = await getHistoricalRates({
    instrument: 'xauusd',
    dates: { from: new Date(`${from}T00:00:00Z`), to: new Date(`${to}T23:59:59Z`) },
    timeframe: 'm15',
    format: 'json',
    priceType: 'bid',
    volumes: true,
    ignoreFlats: false,
    batchSize: 20,
    pauseBetweenBatchesMs: 150
  });
  if (!Array.isArray(rows) || rows.length < 1000) throw new Error(`Unexpected XAU history rows: ${Array.isArray(rows) ? rows.length : typeof rows}`);
  fs.writeFileSync(out, JSON.stringify(rows));
  const first = rows[0], last = rows[rows.length - 1];
  console.log(JSON.stringify({ rows: rows.length, first, last, from, to }, null, 2));
})().catch(err => { console.error(err); process.exit(1); });