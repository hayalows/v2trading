import fs from 'node:fs';
import path from 'node:path';
import { getHistoricalRates } from 'dukascopy-node';

// Targeted bid/ask execution audit. We report BOTH raw absolute-level replay and a
// causal cross-broker basis-adjusted replay. The basis adjustment is a single offset
// estimated from the last completed source M15 close and the last Dukascopy midpoint
// at/before that same pre-entry anchor timestamp. It cannot use future information.

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

function basisOffset(trade, ticks) {
  const source = Number(trade.source_anchor_close);
  const at = new Date(trade.source_anchor_time);
  if (!Number.isFinite(source) || !Number.isFinite(at.getTime())) return { offset: NaN, ageSeconds: NaN };
  let anchor = null;
  for (const x of ticks) {
    if (x.ts <= at) anchor = x;
    else break;
  }
  if (!anchor) return { offset: NaN, ageSeconds: NaN };
  const ageSeconds = (at.getTime() - anchor.ts.getTime()) / 1000;
  if (ageSeconds < 0 || ageSeconds > 300) return { offset: NaN, ageSeconds };
  const mid = (anchor.ask + anchor.bid) / 2;
  return { offset: mid - source, ageSeconds };
}

function replay(trade, ticks, offset = 0) {
  const entry = Number(trade.entry) + offset;
  const stop = Number(trade.stop) + offset;
  const target = Number(trade.target) + offset;
  const direction = trade.direction;
  const start = new Date(trade.entry_time);
  const maxEnd = new Date(start.getTime() + 12 * 3600_000);
  const w = ticks.filter(x => x.ts >= start && x.ts <= maxEnd);
  if (!w.length) return { outcome: 'no_tick_data', filled: false };

  const spreads = w.filter(x => x.ts <= new Date(start.getTime() + 30 * 60_000)).map(x => x.ask - x.bid).filter(Number.isFinite);
  let fillIndex = -1;
  for (let i = 0; i < w.length; i++) {
    // A buy limit is fillable when the ask reaches the level; a sell limit when
    // the bid reaches it. This is intentionally stricter than midpoint OHLC.
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
      if (x.bid <= stop) return { ...spreadStats, outcome: 'loss', filled: true, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString() };
      if (x.bid >= target) return { ...spreadStats, outcome: 'win', filled: true, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString() };
    } else {
      if (x.ask >= stop) return { ...spreadStats, outcome: 'loss', filled: true, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString() };
      if (x.ask <= target) return { ...spreadStats, outcome: 'win', filled: true, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString() };
    }
  }
  return { ...spreadStats, outcome: 'timeout', filled: true, fill_time: fill.ts.toISOString(), exit_time: w[w.length - 1].ts.toISOString() };
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

const manifest = process.argv[2] ?? 'research-output/v03_tick_windows_basis.csv';
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
    const raw = replay(t, ticks, 0);
    const basis = basisOffset(t, ticks);
    const adjusted = Number.isFinite(basis.offset) ? replay(t, ticks, basis.offset) : { outcome: 'no_basis', filled: false };
    const risk = Math.abs(Number(t.entry) - Number(t.stop));
    rows.push({
      setup_id: t.setup_id, symbol: t.symbol, instrument: t.dukascopy_instrument,
      entry_time: t.entry_time, direction: t.direction, m15_outcome: t.m15_outcome,
      source_anchor_time: t.source_anchor_time, source_anchor_close: t.source_anchor_close,
      basis_offset: basis.offset, basis_anchor_age_seconds: basis.ageSeconds,
      raw_tick_outcome: raw.outcome, raw_tick_filled: raw.filled ? 1 : 0,
      adjusted_tick_outcome: adjusted.outcome, adjusted_tick_filled: adjusted.filled ? 1 : 0,
      spread_median: adjusted.spread_median ?? raw.spread_median,
      spread_p90: adjusted.spread_p90 ?? raw.spread_p90,
      spread_p99: adjusted.spread_p99 ?? raw.spread_p99,
      median_spread_as_r: Number.isFinite(adjusted.spread_median ?? raw.spread_median) && risk > 0 ? (adjusted.spread_median ?? raw.spread_median) / risk : NaN,
      p90_spread_as_r: Number.isFinite(adjusted.spread_p90 ?? raw.spread_p90) && risk > 0 ? (adjusted.spread_p90 ?? raw.spread_p90) / risk : NaN,
      adjusted_fill_time: adjusted.fill_time ?? '', adjusted_exit_time: adjusted.exit_time ?? '',
      error: '',
    });
  } catch (e) {
    rows.push({ setup_id: t.setup_id, symbol: t.symbol, instrument: t.dukascopy_instrument, entry_time: t.entry_time,
      direction: t.direction, m15_outcome: t.m15_outcome, raw_tick_outcome: 'fetch_error', raw_tick_filled: 0,
      adjusted_tick_outcome: 'fetch_error', adjusted_tick_filled: 0, error: String(e?.message ?? e) });
  }
}

const cols = ['setup_id','symbol','instrument','entry_time','direction','m15_outcome','source_anchor_time','source_anchor_close','basis_offset','basis_anchor_age_seconds','raw_tick_outcome','raw_tick_filled','adjusted_tick_outcome','adjusted_tick_filled','spread_median','spread_p90','spread_p99','median_spread_as_r','p90_spread_as_r','adjusted_fill_time','adjusted_exit_time','error'];
const csv = [cols.join(','), ...rows.map(r => cols.map(c => String(r[c] ?? '').replaceAll(',', ';')).join(','))].join('\n');
fs.writeFileSync(path.join(outDir, 'v03_tick_execution_audit.csv'), csv);

const ok = rows.filter(r => !r.error);
const rawComparable = ok.filter(r => ['win','loss'].includes(r.raw_tick_outcome) && ['win','loss'].includes(r.m15_outcome));
const adjComparable = ok.filter(r => ['win','loss'].includes(r.adjusted_tick_outcome) && ['win','loss'].includes(r.m15_outcome));
const spreads = ok.map(r => Number(r.median_spread_as_r)).filter(Number.isFinite);
const basisValues = ok.map(r => Number(r.basis_offset)).filter(Number.isFinite);
const summary = {
  requested_trades: selected.length,
  successful_tick_windows: ok.length,
  fetch_errors: rows.length - ok.length,
  basis_available_rate: ok.length ? basisValues.length / ok.length : null,
  raw_tick_fill_rate: ok.length ? ok.filter(r => r.raw_tick_filled === 1).length / ok.length : null,
  adjusted_tick_fill_rate: ok.length ? ok.filter(r => r.adjusted_tick_filled === 1).length / ok.length : null,
  raw_comparable_win_loss: rawComparable.length,
  raw_m15_tick_outcome_agreement: rawComparable.length ? rawComparable.filter(r => r.raw_tick_outcome === r.m15_outcome).length / rawComparable.length : null,
  adjusted_comparable_win_loss: adjComparable.length,
  adjusted_m15_tick_outcome_agreement: adjComparable.length ? adjComparable.filter(r => r.adjusted_tick_outcome === r.m15_outcome).length / adjComparable.length : null,
  median_observed_spread_as_R: spreads.length ? percentile(spreads, 0.50) : null,
  p90_observed_spread_as_R: spreads.length ? percentile(spreads, 0.90) : null,
  note: 'Basis-adjusted replay translates source entry/stop/target by one offset estimated strictly before entry. Spread is still Dukascopy bid/ask and is not basis-adjusted. This is an execution robustness diagnostic, not a broker-equivalence claim.'
};
fs.writeFileSync(path.join(outDir, 'v03_tick_execution_summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
