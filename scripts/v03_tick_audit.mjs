import fs from 'node:fs';
import path from 'node:path';
import { getHistoricalRates } from 'dukascopy-node';

// Targeted bid/ask replay. The goal is not to download years of ticks; it is to
// inspect actual spread and side-specific execution around a stratified sample of
// V2 setups. This script tolerates the common array/object JSON shapes returned by
// dukascopy-node across versions.

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const header = lines[0].split(',');
  return lines.slice(1).filter(Boolean).map(line => {
    const vals = line.split(',');
    return Object.fromEntries(header.map((h, i) => [h, vals[i] ?? '']));
  });
}

function normTick(row) {
  let t, ask, bid, askVol, bidVol;
  if (Array.isArray(row)) {
    [t, ask, bid, askVol, bidVol] = row;
  } else if (row && typeof row === 'object') {
    t = row.timestamp ?? row.time ?? row.date ?? row.datetime ?? row[0];
    ask = row.ask ?? row.askPrice ?? row.a ?? row[1];
    bid = row.bid ?? row.bidPrice ?? row.b ?? row[2];
    askVol = row.askVolume ?? row.askVol ?? row[3];
    bidVol = row.bidVolume ?? row.bidVol ?? row[4];
  }
  const ts = typeof t === 'number' ? new Date(t < 1e12 ? t * 1000 : t) : new Date(t);
  const a = Number(ask), b = Number(bid);
  if (!Number.isFinite(ts.getTime()) || !Number.isFinite(a) || !Number.isFinite(b)) return null;
  return { ts, ask: a, bid: b, askVol: Number(askVol), bidVol: Number(bidVol) };
}

function percentile(a, q) {
  if (!a.length) return NaN;
  const x = [...a].sort((m, n) => m - n);
  const p = (x.length - 1) * q;
  const lo = Math.floor(p), hi = Math.ceil(p);
  if (lo === hi) return x[lo];
  return x[lo] * (hi - p) + x[hi] * (p - lo);
}

function replay(trade, ticks) {
  const entry = Number(trade.entry), stop = Number(trade.stop), target = Number(trade.target);
  const direction = trade.direction;
  const start = new Date(trade.entry_time);
  const maxEnd = new Date(start.getTime() + 12 * 3600_000);
  const w = ticks.filter(x => x.ts >= start && x.ts <= maxEnd);
  if (!w.length) return { outcome: 'no_tick_data', filled: false };

  const spreads = w.filter(x => x.ts <= new Date(start.getTime() + 30 * 60_000)).map(x => x.ask - x.bid).filter(Number.isFinite);
  let fillIndex = -1;
  for (let i = 0; i < w.length; i++) {
    // Side-specific limit execution. Longs cross at the ask; shorts at the bid.
    if ((direction === 'long' && w[i].ask <= entry) || (direction === 'short' && w[i].bid >= entry)) {
      fillIndex = i;
      break;
    }
  }
  const spreadStats = {
    spread_median: percentile(spreads, 0.50),
    spread_p90: percentile(spreads, 0.90),
    spread_p99: percentile(spreads, 0.99),
  };
  if (fillIndex < 0) return { ...spreadStats, outcome: 'no_fill', filled: false };

  const fill = w[fillIndex];
  for (let i = fillIndex; i < w.length; i++) {
    const x = w[i];
    if (direction === 'long') {
      // A long exits on the bid side.
      if (x.bid <= stop) return { ...spreadStats, outcome: 'loss', filled: true, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString(), fill_price_side: fill.ask };
      if (x.bid >= target) return { ...spreadStats, outcome: 'win', filled: true, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString(), fill_price_side: fill.ask };
    } else {
      // A short exits on the ask side.
      if (x.ask >= stop) return { ...spreadStats, outcome: 'loss', filled: true, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString(), fill_price_side: fill.bid };
      if (x.ask <= target) return { ...spreadStats, outcome: 'win', filled: true, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString(), fill_price_side: fill.bid };
    }
  }
  return { ...spreadStats, outcome: 'timeout', filled: true, fill_time: fill.ts.toISOString(), fill_price_side: direction === 'long' ? fill.ask : fill.bid };
}

async function fetchTicks(instrument, from, to) {
  const data = await getHistoricalRates({
    instrument,
    dates: { from: new Date(`${from}T00:00:00Z`), to: new Date(`${to}T00:00:00Z`) },
    timeframe: 'tick',
    format: 'json',
  });
  const raw = Array.isArray(data) ? data : (data?.data ?? data?.rates ?? []);
  return raw.map(normTick).filter(Boolean).sort((a, b) => a.ts - b.ts);
}

const manifest = process.argv[2] ?? 'research-output/v03_tick_windows.csv';
const outDir = process.argv[3] ?? 'research-output';
fs.mkdirSync(outDir, { recursive: true });
const trades = parseCsv(fs.readFileSync(manifest, 'utf8'));
const maxPerSymbol = Number(process.env.TICK_AUDIT_PER_SYMBOL ?? 4);
const counts = new Map();
const selected = trades.filter(t => {
  const n = counts.get(t.symbol) ?? 0;
  if (n >= maxPerSymbol) return false;
  counts.set(t.symbol, n + 1);
  return true;
});

const cache = new Map();
const rows = [];
for (const t of selected) {
  const key = `${t.dukascopy_instrument}|${t.from}|${t.to}`;
  try {
    let ticks = cache.get(key);
    if (!ticks) {
      ticks = await fetchTicks(t.dukascopy_instrument, t.from, t.to);
      cache.set(key, ticks);
    }
    const r = replay(t, ticks);
    const risk = Math.abs(Number(t.entry) - Number(t.stop));
    rows.push({
      setup_id: t.setup_id, symbol: t.symbol, instrument: t.dukascopy_instrument,
      entry_time: t.entry_time, direction: t.direction, m15_outcome: t.m15_outcome,
      tick_outcome: r.outcome, tick_filled: r.filled ? 1 : 0,
      spread_median: r.spread_median, spread_p90: r.spread_p90, spread_p99: r.spread_p99,
      median_spread_as_r: Number.isFinite(r.spread_median) && risk > 0 ? r.spread_median / risk : NaN,
      p90_spread_as_r: Number.isFinite(r.spread_p90) && risk > 0 ? r.spread_p90 / risk : NaN,
      fill_time: r.fill_time ?? '', exit_time: r.exit_time ?? '',
      error: '',
    });
  } catch (e) {
    rows.push({ setup_id: t.setup_id, symbol: t.symbol, instrument: t.dukascopy_instrument, entry_time: t.entry_time,
      direction: t.direction, m15_outcome: t.m15_outcome, tick_outcome: 'fetch_error', tick_filled: 0,
      spread_median: '', spread_p90: '', spread_p99: '', median_spread_as_r: '', p90_spread_as_r: '', fill_time: '', exit_time: '',
      error: String(e?.message ?? e) });
  }
}

const cols = ['setup_id','symbol','instrument','entry_time','direction','m15_outcome','tick_outcome','tick_filled','spread_median','spread_p90','spread_p99','median_spread_as_r','p90_spread_as_r','fill_time','exit_time','error'];
const csv = [cols.join(','), ...rows.map(r => cols.map(c => String(r[c] ?? '').replaceAll(',', ';')).join(','))].join('\n');
fs.writeFileSync(path.join(outDir, 'v03_tick_execution_audit.csv'), csv);

const ok = rows.filter(r => !r.error);
const comparable = ok.filter(r => ['win','loss'].includes(r.tick_outcome) && ['win','loss'].includes(r.m15_outcome));
const spreads = ok.map(r => Number(r.median_spread_as_r)).filter(Number.isFinite);
const summary = {
  requested_trades: selected.length,
  successful_tick_windows: ok.length,
  fetch_errors: rows.length - ok.length,
  tick_fill_rate: ok.length ? ok.filter(r => r.tick_filled === 1).length / ok.length : null,
  comparable_win_loss: comparable.length,
  m15_tick_outcome_agreement: comparable.length ? comparable.filter(r => r.tick_outcome === r.m15_outcome).length / comparable.length : null,
  median_observed_spread_as_R: spreads.length ? percentile(spreads, 0.50) : null,
  p90_observed_spread_as_R: spreads.length ? percentile(spreads, 0.90) : null,
  note: 'Dukascopy bid/ask replay is a cross-broker execution audit. No quote-basis adjustment is applied here, so fill mismatches are diagnostic rather than automatic corrections to the strategy ledger.'
};
fs.writeFileSync(path.join(outDir, 'v03_tick_execution_summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
