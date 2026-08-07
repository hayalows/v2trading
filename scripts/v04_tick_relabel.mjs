import fs from 'node:fs';
import path from 'node:path';
import { getHistoricalRates } from 'dukascopy-node';

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const header = lines[0].split(',');
  return lines.slice(1).filter(Boolean).map(line => {
    const vals = line.split(',');
    return Object.fromEntries(header.map((h, i) => [h, vals[i] ?? '']));
  });
}

function normTick(row) {
  let t, ask, bid;
  if (Array.isArray(row)) [t, ask, bid] = row;
  else if (row && typeof row === 'object') {
    t = row.timestamp ?? row.time ?? row.date ?? row.datetime ?? row[0];
    ask = row.ask ?? row.askPrice ?? row.a ?? row[1];
    bid = row.bid ?? row.bidPrice ?? row.b ?? row[2];
  }
  const ts = typeof t === 'number' ? new Date(t < 1e12 ? t * 1000 : t) : new Date(t);
  const a = Number(ask), b = Number(bid);
  if (!Number.isFinite(ts.getTime()) || !Number.isFinite(a) || !Number.isFinite(b)) return null;
  return { ts, ask: a, bid: b };
}

function percentile(a, q) {
  if (!a.length) return NaN;
  const x = [...a].sort((m, n) => m - n);
  const p = (x.length - 1) * q;
  const lo = Math.floor(p), hi = Math.ceil(p);
  return lo === hi ? x[lo] : x[lo] * (hi - p) + x[hi] * (p - lo);
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
  return { offset: (anchor.ask + anchor.bid) / 2 - source, ageSeconds };
}

function replay(trade, ticks, offset = 0) {
  const sourceEntry = Number(trade.entry) + offset;
  const stop = Number(trade.stop) + offset;
  const target = Number(trade.target) + offset;
  const risk = Math.abs(Number(trade.entry) - Number(trade.stop));
  const direction = trade.direction;
  const start = new Date(trade.entry_time);
  const maxEnd = new Date(start.getTime() + 12 * 3600_000);
  const w = ticks.filter(x => x.ts >= start && x.ts <= maxEnd);
  if (!w.length || !(risk > 0)) return { outcome: 'no_tick_data', filled: false };

  const first30 = w.filter(x => x.ts <= new Date(start.getTime() + 30 * 60_000));
  const spreads = first30.map(x => x.ask - x.bid).filter(Number.isFinite);
  let fillIndex = -1;
  for (let i = 0; i < w.length; i++) {
    if ((direction === 'long' && w[i].ask <= sourceEntry) || (direction === 'short' && w[i].bid >= sourceEntry)) {
      fillIndex = i;
      break;
    }
  }
  const common = {
    spread_median_r: percentile(spreads, 0.50) / risk,
    spread_p90_r: percentile(spreads, 0.90) / risk,
  };
  if (fillIndex < 0) return { ...common, outcome: 'no_fill', filled: false };

  const fill = w[fillIndex];
  const fillPrice = direction === 'long' ? Math.min(fill.ask, sourceEntry) : Math.max(fill.bid, sourceEntry);
  const fillSpreadR = (fill.ask - fill.bid) / risk;
  const fillDelayMs = fill.ts.getTime() - start.getTime();

  for (let i = fillIndex; i < w.length; i++) {
    const x = w[i];
    if (direction === 'long') {
      if (x.bid <= stop) {
        const execR = (x.bid - fillPrice) / risk;
        const stopSlipR = Math.max(0, stop - x.bid) / risk;
        return { ...common, outcome: 'loss', filled: true, fill_price: fillPrice, exit_price: x.bid,
          exec_r: execR, stop_slippage_r: stopSlipR, fill_spread_r: fillSpreadR,
          fill_delay_ms: fillDelayMs, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString() };
      }
      if (x.bid >= target) {
        return { ...common, outcome: 'win', filled: true, fill_price: fillPrice, exit_price: target,
          exec_r: (target - fillPrice) / risk, stop_slippage_r: 0, fill_spread_r: fillSpreadR,
          fill_delay_ms: fillDelayMs, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString() };
      }
    } else {
      if (x.ask >= stop) {
        const execR = (fillPrice - x.ask) / risk;
        const stopSlipR = Math.max(0, x.ask - stop) / risk;
        return { ...common, outcome: 'loss', filled: true, fill_price: fillPrice, exit_price: x.ask,
          exec_r: execR, stop_slippage_r: stopSlipR, fill_spread_r: fillSpreadR,
          fill_delay_ms: fillDelayMs, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString() };
      }
      if (x.ask <= target) {
        return { ...common, outcome: 'win', filled: true, fill_price: fillPrice, exit_price: target,
          exec_r: (fillPrice - target) / risk, stop_slippage_r: 0, fill_spread_r: fillSpreadR,
          fill_delay_ms: fillDelayMs, fill_time: fill.ts.toISOString(), exit_time: x.ts.toISOString() };
      }
    }
  }
  const last = w[w.length - 1];
  const mark = direction === 'long' ? last.bid : last.ask;
  const execR = direction === 'long' ? (mark - fillPrice) / risk : (fillPrice - mark) / risk;
  return { ...common, outcome: 'timeout', filled: true, fill_price: fillPrice, exit_price: mark,
    exec_r: Math.max(-1.5, Math.min(3.0, execR)), stop_slippage_r: 0, fill_spread_r: fillSpreadR,
    fill_delay_ms: fillDelayMs, fill_time: fill.ts.toISOString(), exit_time: last.ts.toISOString() };
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

const manifest = process.argv[2] ?? 'research-output/v04_tick_windows_basis.csv';
const outDir = process.argv[3] ?? 'research-output';
fs.mkdirSync(outDir, { recursive: true });
const trades = parseCsv(fs.readFileSync(manifest, 'utf8'));
const cache = new Map();
const rows = [];

for (const t of trades) {
  const key = `${t.dukascopy_instrument}|${t.from}|${t.to}`;
  try {
    let ticks = cache.get(key);
    if (!ticks) {
      ticks = await fetchTicks(t.dukascopy_instrument, t.from, t.to);
      cache.set(key, ticks);
    }
    const basis = basisOffset(t, ticks);
    const raw = replay(t, ticks, 0);
    const adjusted = Number.isFinite(basis.offset) ? replay(t, ticks, basis.offset) : { outcome: 'no_basis', filled: false };
    const spreadR = Number(adjusted.fill_spread_r);
    const slipR = Number(adjusted.stop_slippage_r ?? 0);
    const quality = !adjusted.filled || !['win','loss'].includes(adjusted.outcome) ? 'unresolved'
      : Number.isFinite(spreadR) && spreadR <= 0.20 && slipR <= 0.10 ? 'trusted'
      : Number.isFinite(spreadR) && spreadR <= 0.35 && slipR <= 0.20 ? 'usable'
      : 'poor';
    rows.push({
      setup_id: t.setup_id, symbol: t.symbol, instrument: t.dukascopy_instrument,
      entry_time: t.entry_time, direction: t.direction, m15_outcome: t.m15_outcome,
      m15_net_r: t.m15_net_r, p_price: t.p_price, score_bin: t.score_bin,
      risk_distance: t.risk_distance, risk_atr: t.risk_atr, source_cost_as_r: t.cost_as_r,
      basis_offset: basis.offset, basis_anchor_age_seconds: basis.ageSeconds,
      raw_tick_outcome: raw.outcome,
      adjusted_tick_outcome: adjusted.outcome,
      adjusted_tick_filled: adjusted.filled ? 1 : 0,
      adjusted_exec_r: adjusted.exec_r,
      fill_spread_r: adjusted.fill_spread_r,
      spread_median_r: adjusted.spread_median_r,
      spread_p90_r: adjusted.spread_p90_r,
      stop_slippage_r: adjusted.stop_slippage_r,
      fill_delay_ms: adjusted.fill_delay_ms,
      fill_time: adjusted.fill_time ?? '', exit_time: adjusted.exit_time ?? '',
      execution_quality: quality, error: '',
    });
  } catch (e) {
    rows.push({ setup_id: t.setup_id, symbol: t.symbol, entry_time: t.entry_time, direction: t.direction,
      m15_outcome: t.m15_outcome, m15_net_r: t.m15_net_r, p_price: t.p_price, score_bin: t.score_bin,
      adjusted_tick_outcome: 'fetch_error', adjusted_tick_filled: 0, execution_quality: 'unresolved',
      error: String(e?.message ?? e) });
  }
}

const cols = [...new Set(rows.flatMap(r => Object.keys(r)))];
const csv = [cols.join(','), ...rows.map(r => cols.map(c => String(r[c] ?? '').replaceAll(',', ';')).join(','))].join('\n');
fs.writeFileSync(path.join(outDir, 'v04_tick_execution_audit.csv'), csv);

const ok = rows.filter(r => !r.error);
const clear = ok.filter(r => r.adjusted_tick_filled === 1 && ['win','loss'].includes(r.adjusted_tick_outcome));
const trusted = clear.filter(r => r.execution_quality === 'trusted');
const spreads = clear.map(r => Number(r.fill_spread_r)).filter(Number.isFinite);
const slippage = clear.map(r => Number(r.stop_slippage_r)).filter(Number.isFinite);
const summary = {
  requested_trades: trades.length,
  successful_windows: ok.length,
  clear_executable_labels: clear.length,
  trusted_labels: trusted.length,
  fill_rate: ok.length ? ok.filter(r => r.adjusted_tick_filled === 1).length / ok.length : null,
  m15_tick_agreement: clear.length ? clear.filter(r => r.adjusted_tick_outcome === r.m15_outcome).length / clear.length : null,
  median_fill_spread_r: spreads.length ? percentile(spreads, .50) : null,
  p90_fill_spread_r: spreads.length ? percentile(spreads, .90) : null,
  median_stop_slippage_r: slippage.length ? percentile(slippage, .50) : null,
  p90_stop_slippage_r: slippage.length ? percentile(slippage, .90) : null,
  note: 'Executable labels use Dukascopy ask for long entries / short exits and bid for short entries / long exits. Basis translation is estimated strictly before entry.'
};
fs.writeFileSync(path.join(outDir, 'v04_tick_execution_summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
