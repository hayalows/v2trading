import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SB_URL = Deno.env.get("SUPABASE_URL");
const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
const db = createClient(SB_URL, KEY, { auth: { persistSession: false } });
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization,x-client-info,apikey,content-type",
  "Access-Control-Allow-Methods": "GET,OPTIONS",
  "Cache-Control": "no-store",
};
const SYMBOLS = ["EURUSD", "GBPUSD"];
const YAHOO = { EURUSD: "EURUSD=X", GBPUSD: "GBPUSD=X" };
const ORIGINAL_WINDOW_BARS = 8;
const EXTENDED_WINDOW_BARS = 48;
const RESEARCH_TAIL_BARS = 192;
const SHADOW_ENTRY_HORIZON_BARS = 192;
const MAX_HOLD_BARS = 48;
const STOP_BUFFER_ATR = 0.03;
const REWARD_R = 2.5;
const MIN_RISK_ATR = 0.08;
const MAX_RISK_ATR = 1.60;
const HISTORY_RECOVERY_HOURS = 6;
const PRICE_EPS = 1e-9;
const V20_PROSPECTIVE_START = "2026-08-11T15:25:00.000Z";
const DEPTH_PCTS = Array.from({ length: 21 }, (_, i) => i * 5);
const PENETRATION_THRESHOLDS = [0, 10, 20, 30, 40, 45, 50, 65, 85, 100];

const reply = (x, status = 200) => new Response(JSON.stringify(x), { status, headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" } });
const number = (v) => v === null || v === undefined || v === "" ? null : (Number.isFinite(Number(v)) ? Number(v) : null);
const ms = (t) => new Date(t).getTime();
const touch = (b, p) => b.low <= p + PRICE_EPS && p <= b.high + PRICE_EPS;
const zoneTouch = (b, lo, hi) => b.low <= hi + PRICE_EPS && b.high + PRICE_EPS >= lo;
const floor15 = (t) => new Date(Math.floor(ms(t) / 900000) * 900000).toISOString();
const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
const isProspective = (t) => ms(t.armed_at) >= ms(V20_PROSPECTIVE_START);

function trueRanges(bars) {
  return bars.map((b, i) => i === 0 ? b.high - b.low : Math.max(b.high - b.low, Math.abs(b.high - bars[i - 1].close), Math.abs(b.low - bars[i - 1].close)));
}
function rollingMean(xs, n) {
  let sum = 0;
  return xs.map((x, i) => { sum += x; if (i >= n) sum -= xs[i - n]; return sum / Math.min(i + 1, n); });
}
function poiPenetration(t, b) {
  const lo = Number(t.poi_low), hi = Number(t.poi_high), width = hi - lo;
  if (!(width > 0)) return null;
  return t.direction === "long" ? (hi - b.low) / width : (b.high - lo) / width;
}
function distalClose(t, b) {
  return t.direction === "long" ? b.close < Number(t.poi_low) - PRICE_EPS : b.close > Number(t.poi_high) + PRICE_EPS;
}
function lifecycleState(zoneIdx, fillIdx, maxPen, distalCloseIdx) {
  if (distalCloseIdx >= 0) return "invalidated_close_through";
  if (zoneIdx < 0) return "untouched";
  if (fillIdx >= 0) return maxPen >= 1 ? "distal_touched" : "midpoint_touched";
  if (maxPen >= 1) return "distal_touched";
  if (maxPen >= .5) return "deep_unfilled";
  if (maxPen >= .25) return "partially_mitigated";
  return "grazed";
}

async function loadBars(symbol, limit = 2500) {
  const q = await db.from("market_bars").select("ts,open,high,low,close").eq("symbol", symbol).eq("timeframe", "15m").order("ts", { ascending: false }).limit(limit);
  if (q.error) throw new Error(`${symbol} bars: ${q.error.message}`);
  const uniq = new Map();
  for (const r of (q.data || []).reverse()) {
    const open = number(r.open), high = number(r.high), low = number(r.low), close = number(r.close);
    if (open == null || high == null || low == null || close == null || high < low) continue;
    const ts = new Date(r.ts).toISOString();
    uniq.set(ts, { ts, open, high, low, close });
  }
  return [...uniq.values()].sort((a, b) => ms(a.ts) - ms(b.ts));
}

async function load5m(symbol) {
  let last = "";
  for (const host of ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]) {
    try {
      const url = `https://${host}/v8/finance/chart/${encodeURIComponent(YAHOO[symbol])}?interval=5m&range=5d&includePrePost=false`;
      const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0 V2PaperResearch/2.0", "Accept": "application/json" } });
      if (!r.ok) { last = `${host}:${r.status}`; continue; }
      const j = await r.json(), root = j?.chart?.result?.[0], q = root?.indicators?.quote?.[0] || {};
      if (!root?.timestamp?.length) continue;
      const out = [];
      for (let i = 0; i < root.timestamp.length; i++) {
        const open = number(q.open?.[i]), high = number(q.high?.[i]), low = number(q.low?.[i]), close = number(q.close?.[i]);
        if (open == null || high == null || low == null || close == null || high < low) continue;
        const ts = new Date(root.timestamp[i] * 1000).toISOString();
        if (Date.now() >= ms(ts) + 300000) out.push({ ts, open, high, low, close });
      }
      return out;
    } catch (e) { last = String(e); }
  }
  throw new Error(`5m path unavailable ${last}`);
}
async function cached5m(symbol, cache) {
  if (cache[symbol] !== undefined) return cache[symbol];
  try { cache[symbol] = await load5m(symbol); } catch { cache[symbol] = null; }
  return cache[symbol];
}

async function eventOnce(tradeKey, type, at, price = null, payload = {}) {
  const old = await db.from("paper_trade_events").select("id").eq("trade_key", tradeKey).eq("event_type", type).limit(1).maybeSingle();
  if (old.data) return;
  const w = await db.from("paper_trade_events").insert({ trade_key: tradeKey, event_at: at, event_type: type, price, payload });
  if (w.error) throw new Error(`event ${type}: ${w.error.message}`);
}

function currentCandidate(r) {
  return { symbol: r.symbol, stage: r.formation_stage, code: r.formation_code, direction: r.formation_direction, low: r.poi_low, high: r.poi_high, session: r.market_session, regime: r.regime, trends: { d1: r.d1_trend, h4: r.h4_trend, h1: r.h1_trend, m15: r.m15_trend }, diagnostics: r.details?.diagnostics || {}, form: r.details?.formation || {}, sourceAt: r.updated_at, recovered: false };
}
function historyCandidate(r) {
  const f = r.state?.formation || {}, t = r.state?.trends || {};
  return { symbol: r.symbol, stage: r.formation_stage, code: r.formation_code, direction: r.formation_direction, low: f.poiLow, high: f.poiHigh, session: r.state?.session || null, regime: r.regime, trends: { d1: t.d1?.label, h4: t.h4?.label, h1: t.h1?.label, m15: t.m15?.label }, diagnostics: r.state?.diagnostics || {}, form: f.details || {}, sourceAt: r.as_of, recovered: true };
}

async function campaignKey(c) {
  const q = await db.from("formation_campaigns").select("campaign_key,started_at,ended_at").eq("symbol", c.symbol).eq("direction", c.direction).order("started_at", { ascending: false }).limit(20);
  const sweep = ms(c.form.sweepTime);
  return (q.data || []).find(x => ms(x.started_at) <= sweep && (!x.ended_at || sweep <= ms(x.ended_at)))?.campaign_key || null;
}

async function armCandidate(c, bars) {
  const low = number(c.low), high = number(c.high), sweep = c.form?.sweepTime, bos = c.form?.bosTime, poi = c.form?.poiTime;
  if (Number(c.stage) < 6 || !["long", "short"].includes(c.direction) || c.form?.fresh !== true || !sweep || !bos || low == null || high == null || high <= low) return null;
  const tradeKey = `${c.symbol}:${c.direction}:${new Date(sweep).toISOString()}`;
  const old = await db.from("paper_trades").select("trade_key").eq("trade_key", tradeKey).maybeSingle();
  if (old.data) return null;
  const sweepIdx = bars.findIndex(b => b.ts === new Date(sweep).toISOString()), bosIdx = bars.findIndex(b => b.ts === new Date(bos).toISOString());
  if (sweepIdx < 0 || bosIdx <= sweepIdx) return null;
  const atr = rollingMean(trueRanges(bars), 14)[sweepIdx];
  if (!Number.isFinite(atr) || atr <= 0) return null;
  const entry = (low + high) / 2;
  const extreme = c.direction === "long" ? bars[sweepIdx].low : bars[sweepIdx].high;
  const stop = c.direction === "long" ? extreme - STOP_BUFFER_ATR * atr : extreme + STOP_BUFFER_ATR * atr;
  const risk = c.direction === "long" ? entry - stop : stop - entry;
  const riskAtr = risk / atr;
  const target = c.direction === "long" ? entry + REWARD_R * risk : entry - REWARD_R * risk;
  const valid = risk > 0 && riskAtr >= MIN_RISK_ATR && riskAtr <= MAX_RISK_ATR;
  const now = new Date().toISOString();
  const row = {
    trade_key: tradeKey, symbol: c.symbol, campaign_key: await campaignKey(c), episode_key: tradeKey, direction: c.direction,
    status: valid ? "armed" : "invalid", armed_at: now, sweep_time: new Date(sweep).toISOString(), bos_time: new Date(bos).toISOString(), poi_time: poi ? new Date(poi).toISOString() : null,
    entry_expires_at: null, poi_low: low, poi_high: high, entry_price: entry, stop_price: stop, target_price: target, sweep_extreme: extreme, atr_at_plan: atr, risk_distance: risk, risk_atr: riskAtr, reward_r: REWARD_R,
    lifecycle_phase: "fresh_wait", pending_age_bars: 0, setup_condition: "intact", research_tail_bars: RESEARCH_TAIL_BARS,
    poi_lifecycle_state: "untouched", max_poi_penetration: 0, focus_active: valid,
    context: { formation_stage: c.stage, formation_code: c.code, market_session: c.session, regime: c.regime, trends: c.trends, diagnostics: c.diagnostics, recovered_from_history: c.recovered, recovered_as_of: c.recovered ? c.sourceAt : null, entry_rule: "baseline: first future completed M15 bar after BOS touching 50% POI midpoint; no time-only invalidation", v20_poi_learning: true, invalid_reason: valid ? null : `risk_atr ${riskAtr.toFixed(3)} outside ${MIN_RISK_ATR}-${MAX_RISK_ATR}` },
  };
  const w = await db.from("paper_trades").insert(row);
  if (w.error) throw new Error(`arm ${tradeKey}: ${w.error.message}`);
  await eventOnce(tradeKey, valid ? "armed" : "invalid", now, valid ? entry : null, { entry, stop, target, riskAtr, poiLow: low, poiHigh: high, recoveredFromHistory: c.recovered });
}

function hits(t, b) {
  return { entry: touch(b, Number(t.entry_price)), stop: t.direction === "long" ? b.low <= Number(t.stop_price) + PRICE_EPS : b.high >= Number(t.stop_price) - PRICE_EPS, target: t.direction === "long" ? b.high >= Number(t.target_price) - PRICE_EPS : b.low <= Number(t.target_price) + PRICE_EPS };
}
function levelHits(direction, b, stop, target) {
  return direction === "long"
    ? { stop: b.low <= stop + PRICE_EPS, target: b.high >= target - PRICE_EPS }
    : { stop: b.high >= stop - PRICE_EPS, target: b.low <= target + PRICE_EPS };
}

async function resolve5mLevels(symbol, direction, entry, stop, target, bar, needsEntry, priorEntryAt, cache) {
  const rows = await cached5m(symbol, cache);
  if (!rows) return { kind: "ambiguous", reason: "5m public path unavailable" };
  const start = ms(bar.ts), sub = rows.filter(x => ms(x.ts) >= start && ms(x.ts) < start + 900000);
  if (!sub.length) return { kind: "ambiguous", reason: "no completed 5m path" };
  let entered = !needsEntry, entryAt = needsEntry ? null : priorEntryAt;
  for (const b of sub) {
    if (!entered) {
      if (!touch(b, entry)) continue;
      const h0 = levelHits(direction, b, stop, target);
      if (h0.stop || h0.target) return { kind: "ambiguous", reason: "entry and exit level touched in same 5m bar" };
      entered = true; entryAt = b.ts; continue;
    }
    const h = levelHits(direction, b, stop, target);
    if (h.stop && h.target) return { kind: "ambiguous", reason: "SL and TP touched in same 5m bar", entryAt };
    if (h.stop) return { kind: "loss", entryAt, exitAt: b.ts, exitPrice: stop };
    if (h.target) return { kind: "win", entryAt, exitAt: b.ts, exitPrice: target };
  }
  return entered ? { kind: "open", entryAt: entryAt || bar.ts } : { kind: "ambiguous", reason: "M15 entry touch not reproduced by 5m path" };
}
async function resolve5m(t, bar, needsEntry, cache) {
  return resolve5mLevels(t.symbol, t.direction, Number(t.entry_price), Number(t.stop_price), Number(t.target_price), bar, needsEntry, t.entry_at, cache);
}

function excursions(t, bars, entryIdx, exitIdx) {
  const xs = bars.slice(entryIdx, exitIdx + 1), entry = Number(t.entry_price), risk = Number(t.risk_distance);
  if (!xs.length || risk <= 0) return { mfe: null, mae: null };
  const hi = Math.max(...xs.map(x => x.high)), lo = Math.min(...xs.map(x => x.low));
  return t.direction === "long" ? { mfe: (hi - entry) / risk, mae: (entry - lo) / risk } : { mfe: (entry - lo) / risk, mae: (hi - entry) / risk };
}

async function finish(t, status, at, price, bars, entryIdx, exitIdx, resolution = "15m", reason = null) {
  const ex = excursions(t, bars, entryIdx, exitIdx), gross = status === "win" ? REWARD_R : status === "loss" ? -1 : null;
  const w = await db.from("paper_trades").update({ status, lifecycle_phase: "closed", focus_active: false, exit_at: at, exit_price: price, gross_r: gross, bars_held: exitIdx - entryIdx + 1, mfe_r: ex.mfe, mae_r: ex.mae, resolution_timeframe: resolution, ambiguous_reason: reason, updated_at: new Date().toISOString() }).eq("trade_key", t.trade_key);
  if (w.error) throw new Error(`finish ${t.trade_key}: ${w.error.message}`);
  await eventOnce(t.trade_key, status, at, price, { grossR: gross, mfeR: ex.mfe, maeR: ex.mae, resolution, reason });
}

function waitingMetrics(t, bars, bosIdx) {
  const seq = bars.slice(bosIdx + 1), entry = Number(t.entry_price), lo = Number(t.poi_low), hi = Number(t.poi_high), risk = Number(t.risk_distance);
  const fillIdx = seq.findIndex(b => touch(b, entry)), zoneIdx = seq.findIndex(b => zoneTouch(b, lo, hi));
  const pre = fillIdx >= 0 ? seq.slice(0, fillIdx) : seq;
  const observed = fillIdx >= 0 ? seq.slice(0, fillIdx + 1) : seq;
  let favorableR = 0;
  if (pre.length && risk > 0) {
    const high = Math.max(...pre.map(b => b.high)), low = Math.min(...pre.map(b => b.low));
    favorableR = t.direction === "long" ? (high - entry) / risk : (entry - low) / risk;
    favorableR = Math.max(0, favorableR);
  }
  const targetReached = favorableR >= REWARD_R;
  const shallow = zoneIdx >= 0 && (fillIdx < 0 || zoneIdx < fillIdx);
  const condition = shallow && targetReached ? "partially_mitigated_after_target" : shallow ? "partially_mitigated" : targetReached ? "target_delivered_before_entry" : "intact";
  const age = seq.length;
  const phase = age <= ORIGINAL_WINDOW_BARS ? "fresh_wait" : age <= EXTENDED_WINDOW_BARS ? "extended_wait" : age <= RESEARCH_TAIL_BARS ? "long_tail_wait" : "outside_studied_tail";
  let maxPen = 0, maxPenIdx = -1, distalCloseIdx = -1;
  for (let i = 0; i < observed.length; i++) {
    const p = poiPenetration(t, observed[i]);
    if (p != null && p > maxPen) { maxPen = p; maxPenIdx = i; }
    if (distalCloseIdx < 0 && distalClose(t, observed[i])) distalCloseIdx = i;
  }
  const poiState = lifecycleState(zoneIdx, fillIdx, maxPen, distalCloseIdx);
  return { seq, fillIdx, zoneIdx, age, favorableR, targetReached, shallow, condition, phase, maxPen: Math.max(0, maxPen), maxPenIdx, maxPenAt: maxPenIdx >= 0 ? observed[maxPenIdx]?.ts : null, distalCloseIdx, distalCloseAt: distalCloseIdx >= 0 ? observed[distalCloseIdx]?.ts : null, poiState };
}

async function recordPenetrationEvents(t, m) {
  if (!m.seq.length) return;
  const prospective = isProspective(t), rows = [];
  for (const thresholdPct of PENETRATION_THRESHOLDS) {
    const threshold = thresholdPct / 100;
    let idx = -1, p = null;
    for (let i = 0; i < m.seq.length; i++) {
      const q = poiPenetration(t, m.seq[i]);
      if (q != null && q + 1e-12 >= threshold) { idx = i; p = q; break; }
    }
    if (idx < 0) continue;
    rows.push({
      event_key: `${t.trade_key}:${thresholdPct}`,
      trade_key: t.trade_key,
      symbol: t.symbol,
      direction: t.direction,
      threshold_pct: thresholdPct,
      prospective,
      reached_at: m.seq[idx].ts,
      age_bars: idx + 1,
      observed_penetration: p,
      before_midpoint: m.fillIdx < 0 || idx < m.fillIdx,
      payload: { baseline_midpoint: Number(t.entry_price), poi_low: Number(t.poi_low), poi_high: Number(t.poi_high), v20: true },
    });
  }
  if (!rows.length) return;
  const w = await db.from("poi_penetration_events").upsert(rows, { onConflict: "event_key", ignoreDuplicates: true });
  if (w.error) throw new Error(`penetration events ${t.trade_key}: ${w.error.message}`);
}

async function updateWaiting(t, m) {
  const firstZone = m.zoneIdx >= 0 ? m.seq[m.zoneIdx]?.ts : null;
  const context = { ...(t.context || {}), v20_poi_learning: true, v14_waiting_research: true, v14_reactivation_pending: false, time_only_invalidation: false, old_8_bar_window_passed: m.age > ORIGINAL_WINDOW_BARS, waiting_evidence: m.phase === "outside_studied_tail" ? "outside studied 48h tail" : "within studied public-proxy tail", max_poi_penetration: m.maxPen };
  const patch = { status: "armed", entry_expires_at: null, lifecycle_phase: m.phase, pending_age_bars: m.age, first_zone_touch_at: t.first_zone_touch_at || firstZone, first_zone_touch_bar: t.first_zone_touch_bar || (m.zoneIdx >= 0 ? m.zoneIdx + 1 : null), pre_entry_max_favorable_r: m.favorableR, pre_entry_target_reached: m.targetReached, setup_condition: m.condition, research_tail_bars: RESEARCH_TAIL_BARS, poi_lifecycle_state: m.poiState, max_poi_penetration: m.maxPen, max_poi_penetration_at: m.maxPenAt, distal_close_at: t.distal_close_at || m.distalCloseAt, context, updated_at: new Date().toISOString() };
  const w = await db.from("paper_trades").update(patch).eq("trade_key", t.trade_key);
  if (w.error) throw new Error(`waiting ${t.trade_key}: ${w.error.message}`);
  await recordPenetrationEvents({ ...t, ...patch }, m);
  const at = m.seq.at(-1)?.ts || new Date().toISOString();
  if (t.status === "expired" || t.context?.v14_reactivation_pending) await eventOnce(t.trade_key, "reactivated_v14", at, null, { reason: "8-bar expiry removed after waiting-time study" });
  if (m.phase !== (t.lifecycle_phase || "fresh_wait")) await eventOnce(t.trade_key, m.phase, at, null, { ageBars: m.age });
  if (m.shallow && !t.first_zone_touch_at) await eventOnce(t.trade_key, "partially_mitigated", firstZone || at, null, { ageBars: m.zoneIdx + 1, maxPenetration: m.maxPen });
  if (m.targetReached && !t.pre_entry_target_reached) await eventOnce(t.trade_key, "target_delivered_before_entry", at, Number(t.target_price), { preEntryMaxFavorableR: m.favorableR });
}

async function evaluate(t, bars, m5Cache) {
  const bosIdx = bars.findIndex(b => b.ts === new Date(t.bos_time).toISOString());
  if (bosIdx < 0) return;
  if (t.status === "armed" || t.status === "expired") {
    const m = waitingMetrics(t, bars, bosIdx);
    if (m.fillIdx < 0) { await updateWaiting(t, m); return; }
    const entryIdx = bosIdx + 1 + m.fillIdx, bar = bars[entryIdx], h = hits(t, bar), barsToEntry = entryIdx - bosIdx;
    await recordPenetrationEvents(t, m);
    const base = { status: "open", lifecycle_phase: "filled", entry_at: bar.ts, bars_to_entry: barsToEntry, pending_age_bars: barsToEntry, entry_expires_at: null, first_zone_touch_at: t.first_zone_touch_at || (m.zoneIdx >= 0 ? m.seq[m.zoneIdx]?.ts : null), first_zone_touch_bar: t.first_zone_touch_bar || (m.zoneIdx >= 0 ? m.zoneIdx + 1 : null), pre_entry_max_favorable_r: m.favorableR, pre_entry_target_reached: m.targetReached, setup_condition: m.condition, poi_lifecycle_state: m.maxPen >= 1 ? "distal_touched" : "midpoint_touched", max_poi_penetration: Math.max(.5, m.maxPen), max_poi_penetration_at: m.maxPenAt || bar.ts, focus_active: true, context: { ...(t.context || {}), v20_poi_learning: true, v14_waiting_research: true, v14_reactivation_pending: false, time_only_invalidation: false, old_8_bar_window_passed: barsToEntry > ORIGINAL_WINDOW_BARS }, updated_at: new Date().toISOString() };
    if (h.stop || h.target) {
      const r = await resolve5m({ ...t, ...base }, bar, true, m5Cache);
      if (r.kind === "ambiguous") { await finish({ ...t, ...base }, "ambiguous", bar.ts, null, bars, entryIdx, entryIdx, "5m", r.reason); return; }
      const entryAt = r.entryAt || bar.ts, ctx = { ...base.context, entry_bar_resolved_5m: true };
      const w = await db.from("paper_trades").update({ ...base, status: r.kind === "open" ? "open" : r.kind, entry_at: entryAt, resolution_timeframe: "5m", context: ctx }).eq("trade_key", t.trade_key);
      if (w.error) throw new Error(w.error.message);
      await eventOnce(t.trade_key, "entry", entryAt, Number(t.entry_price), { barsToEntry, resolution: "5m", lifecyclePhase: m.phase, setupCondition: m.condition, maxPenetration: m.maxPen });
      if (r.kind === "win" || r.kind === "loss") await finish({ ...t, ...base, context: ctx }, r.kind, r.exitAt, r.exitPrice, bars, entryIdx, entryIdx, "5m");
      return;
    }
    const w = await db.from("paper_trades").update({ ...base, resolution_timeframe: "15m" }).eq("trade_key", t.trade_key);
    if (w.error) throw new Error(w.error.message);
    await eventOnce(t.trade_key, "entry", bar.ts, Number(t.entry_price), { barsToEntry, resolution: "15m", lifecyclePhase: m.phase, setupCondition: m.condition, timeSemantics: "M15 containing first midpoint touch", maxPenetration: m.maxPen });
    return;
  }
  if (t.status !== "open" || !t.entry_at) return;
  const entryIdx = bars.findIndex(b => b.ts === floor15(t.entry_at));
  if (entryIdx < 0) return;
  const lastIdx = Math.min(bars.length - 1, entryIdx + MAX_HOLD_BARS), firstIdx = t.context?.entry_bar_resolved_5m ? entryIdx + 1 : entryIdx;
  for (let i = firstIdx; i <= lastIdx; i++) {
    const h = hits(t, bars[i]);
    if (h.stop && h.target) {
      const r = await resolve5m(t, bars[i], false, m5Cache);
      if (r.kind === "ambiguous") { await finish(t, "ambiguous", bars[i].ts, null, bars, entryIdx, i, "5m", r.reason); return; }
      await finish(t, r.kind, r.exitAt, r.exitPrice, bars, entryIdx, i, "5m"); return;
    }
    if (h.stop) { await finish(t, "loss", bars[i].ts, Number(t.stop_price), bars, entryIdx, i); return; }
    if (h.target) { await finish(t, "win", bars[i].ts, Number(t.target_price), bars, entryIdx, i); return; }
  }
  const ex = excursions(t, bars, entryIdx, lastIdx);
  if (bars.length - 1 >= entryIdx + MAX_HOLD_BARS) {
    const b = bars[entryIdx + MAX_HOLD_BARS], rawR = t.direction === "long" ? (b.close - Number(t.entry_price)) / Number(t.risk_distance) : (Number(t.entry_price) - b.close) / Number(t.risk_distance), gross = clamp(rawR, -1, REWARD_R);
    const w = await db.from("paper_trades").update({ status: "timeout", lifecycle_phase: "closed", focus_active: false, exit_at: b.ts, exit_price: b.close, gross_r: gross, bars_held: MAX_HOLD_BARS + 1, mfe_r: ex.mfe, mae_r: ex.mae, resolution_timeframe: "15m", updated_at: new Date().toISOString() }).eq("trade_key", t.trade_key);
    if (w.error) throw new Error(w.error.message);
    await eventOnce(t.trade_key, "timeout", b.ts, b.close, { grossR: gross, mfeR: ex.mfe, maeR: ex.mae }); return;
  }
  await db.from("paper_trades").update({ mfe_r: ex.mfe, mae_r: ex.mae, bars_held: lastIdx - entryIdx + 1, updated_at: new Date().toISOString() }).eq("trade_key", t.trade_key);
}

async function ensureDepthShadows(t) {
  const q = await db.from("poi_depth_shadow").select("depth_pct").eq("trade_key", t.trade_key);
  if (q.error) throw new Error(`depth read ${t.trade_key}: ${q.error.message}`);
  const have = new Set((q.data || []).map(x => Number(x.depth_pct))), rows = [], lo = Number(t.poi_low), hi = Number(t.poi_high), stop = Number(t.stop_price), atr = Number(t.atr_at_plan), prospective = isProspective(t), frozenAt = new Date().toISOString();
  for (const depthPct of DEPTH_PCTS) {
    if (have.has(depthPct)) continue;
    const d = depthPct / 100, entry = t.direction === "long" ? hi - d * (hi - lo) : lo + d * (hi - lo);
    const risk = t.direction === "long" ? entry - stop : stop - entry, riskAtr = atr > 0 ? risk / atr : NaN;
    const eligible = Number.isFinite(riskAtr) && risk > 0 && riskAtr >= MIN_RISK_ATR && riskAtr <= MAX_RISK_ATR;
    const target = t.direction === "long" ? entry + REWARD_R * risk : entry - REWARD_R * risk;
    rows.push({ shadow_key: `${t.trade_key}:${depthPct}`, trade_key: t.trade_key, symbol: t.symbol, direction: t.direction, depth_pct: depthPct, prospective, frozen_at: frozenAt, eligible, status: eligible ? "waiting" : "ineligible", entry_price: entry, stop_price: stop, target_price: target, risk_distance: risk, risk_atr: riskAtr, updated_at: frozenAt });
  }
  if (!rows.length) return;
  const w = await db.from("poi_depth_shadow").insert(rows);
  if (w.error) throw new Error(`depth freeze ${t.trade_key}: ${w.error.message}`);
}

async function closeShadow(s, patch) {
  const w = await db.from("poi_depth_shadow").update({ ...patch, updated_at: new Date().toISOString() }).eq("shadow_key", s.shadow_key);
  if (w.error) throw new Error(`shadow close ${s.shadow_key}: ${w.error.message}`);
}

async function evaluateShadow(s, parent, bars, m5Cache) {
  if (!s.eligible || s.status === "ineligible") return;
  const bosIdx = bars.findIndex(b => b.ts === new Date(parent.bos_time).toISOString());
  if (bosIdx < 0) return;
  const entry = Number(s.entry_price), stop = Number(s.stop_price), target = Number(s.target_price), risk = Number(s.risk_distance);
  if (s.status === "waiting") {
    const seq = bars.slice(bosIdx + 1), k = seq.findIndex(b => touch(b, entry));
    if (k < 0) {
      if (seq.length >= SHADOW_ENTRY_HORIZON_BARS) {
        const b = seq[SHADOW_ENTRY_HORIZON_BARS - 1];
        await closeShadow(s, { status: "not_filled", exit_at: b.ts, gross_r: 0, resolution_timeframe: "15m", ambiguous_reason: null });
      }
      return;
    }
    const entryIdx = bosIdx + 1 + k, bar = bars[entryIdx], h = levelHits(s.direction, bar, stop, target), barsToEntry = entryIdx - bosIdx;
    if (h.stop || h.target) {
      const r = await resolve5mLevels(s.symbol, s.direction, entry, stop, target, bar, true, null, m5Cache);
      if (r.kind === "ambiguous") { await closeShadow(s, { status: "ambiguous", filled_at: bar.ts, exit_at: bar.ts, bars_to_entry: barsToEntry, bars_held: 1, resolution_timeframe: "5m", ambiguous_reason: r.reason, gross_r: null }); return; }
      if (r.kind === "win" || r.kind === "loss") { await closeShadow(s, { status: r.kind, filled_at: r.entryAt || bar.ts, exit_at: r.exitAt, exit_price: r.exitPrice, gross_r: r.kind === "win" ? REWARD_R : -1, bars_to_entry: barsToEntry, bars_held: 1, resolution_timeframe: "5m", ambiguous_reason: null }); return; }
      const w = await db.from("poi_depth_shadow").update({ status: "open", filled_at: r.entryAt || bar.ts, bars_to_entry: barsToEntry, resolution_timeframe: "5m", updated_at: new Date().toISOString() }).eq("shadow_key", s.shadow_key);
      if (w.error) throw new Error(w.error.message); return;
    }
    const w = await db.from("poi_depth_shadow").update({ status: "open", filled_at: bar.ts, bars_to_entry: barsToEntry, resolution_timeframe: "15m", updated_at: new Date().toISOString() }).eq("shadow_key", s.shadow_key);
    if (w.error) throw new Error(w.error.message); return;
  }
  if (s.status !== "open" || !s.filled_at) return;
  const entryIdx = bars.findIndex(b => b.ts === floor15(s.filled_at));
  if (entryIdx < 0) return;
  const lastIdx = Math.min(bars.length - 1, entryIdx + MAX_HOLD_BARS);
  for (let i = entryIdx; i <= lastIdx; i++) {
    const h = levelHits(s.direction, bars[i], stop, target);
    if (h.stop && h.target) {
      const r = await resolve5mLevels(s.symbol, s.direction, entry, stop, target, bars[i], false, s.filled_at, m5Cache);
      if (r.kind === "ambiguous") { await closeShadow(s, { status: "ambiguous", exit_at: bars[i].ts, bars_held: i - entryIdx + 1, resolution_timeframe: "5m", ambiguous_reason: r.reason, gross_r: null }); return; }
      if (r.kind === "win" || r.kind === "loss") { await closeShadow(s, { status: r.kind, exit_at: r.exitAt, exit_price: r.exitPrice, gross_r: r.kind === "win" ? REWARD_R : -1, bars_held: i - entryIdx + 1, resolution_timeframe: "5m", ambiguous_reason: null }); return; }
    }
    if (h.stop) { await closeShadow(s, { status: "loss", exit_at: bars[i].ts, exit_price: stop, gross_r: -1, bars_held: i - entryIdx + 1, resolution_timeframe: "15m", ambiguous_reason: null }); return; }
    if (h.target) { await closeShadow(s, { status: "win", exit_at: bars[i].ts, exit_price: target, gross_r: REWARD_R, bars_held: i - entryIdx + 1, resolution_timeframe: "15m", ambiguous_reason: null }); return; }
  }
  if (bars.length - 1 >= entryIdx + MAX_HOLD_BARS) {
    const b = bars[entryIdx + MAX_HOLD_BARS], rawR = s.direction === "long" ? (b.close - entry) / risk : (entry - b.close) / risk;
    await closeShadow(s, { status: "timeout", exit_at: b.ts, exit_price: b.close, gross_r: clamp(rawR, -1, REWARD_R), bars_held: MAX_HOLD_BARS + 1, resolution_timeframe: "15m", ambiguous_reason: null });
  }
}

async function applyFocusSemantics(plans) {
  const groups = new Map();
  for (const t of plans) {
    const k = `${t.symbol}:${t.direction}`;
    const arr = groups.get(k) || []; arr.push(t); groups.set(k, arr);
  }
  for (const arr of groups.values()) {
    arr.sort((a, b) => ms(b.sweep_time) - ms(a.sweep_time));
    const latest = arr[0];
    for (const t of arr) {
      let active = false, reason = null, superseded = null;
      if (t.status === "open") active = true;
      else if (t.status === "armed") {
        if (t.trade_key !== latest.trade_key) { active = false; reason = "superseded_by_newer_same_direction_plan"; superseded = latest.trade_key; }
        else if (t.poi_lifecycle_state === "invalidated_close_through") { active = false; reason = "distal_close_invalidated"; }
        else if (t.lifecycle_phase === "outside_studied_tail") { active = false; reason = "outside_studied_tail"; }
        else active = true;
      }
      if (Boolean(t.focus_active) === active && (t.focus_suppression_reason || null) === reason && (t.superseded_by_trade_key || null) === superseded) continue;
      const w = await db.from("paper_trades").update({ focus_active: active, focus_suppression_reason: reason, superseded_by_trade_key: superseded, updated_at: new Date().toISOString() }).eq("trade_key", t.trade_key);
      if (w.error) throw new Error(`focus semantics ${t.trade_key}: ${w.error.message}`);
    }
  }
}

async function runEngine() {
  const current = await db.from("market_states").select("*").in("symbol", SYMBOLS);
  if (current.error) throw new Error(current.error.message);
  const since = new Date(Date.now() - HISTORY_RECOVERY_HOURS * 3600000).toISOString();
  const hist = await db.from("market_state_history").select("symbol,as_of,formation_stage,formation_code,formation_direction,regime,state").in("symbol", SYMBOLS).gte("formation_stage", 6).gte("as_of", since).order("as_of", { ascending: false }).limit(180);
  if (hist.error) throw new Error(hist.error.message);
  const cache = {}, m5Cache = {}, seen = new Set(), candidates = [...(current.data || []).map(currentCandidate), ...(hist.data || []).map(historyCandidate)];
  for (const c of candidates) {
    const sweep = c.form?.sweepTime, key = sweep ? `${c.symbol}:${c.direction}:${new Date(sweep).toISOString()}` : null;
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    cache[c.symbol] ||= await loadBars(c.symbol);
    await armCandidate(c, cache[c.symbol]);
  }

  const plansQ = await db.from("paper_trades").select("*").in("symbol", SYMBOLS).order("armed_at", { ascending: false }).limit(100);
  if (plansQ.error) throw new Error(plansQ.error.message);
  const plans = plansQ.data || [], byKey = new Map(plans.map(t => [t.trade_key, t]));
  for (const t of plans) await ensureDepthShadows(t);

  const active = plans.filter(t => ["armed", "expired", "open"].includes(t.status)).sort((a, b) => ms(a.armed_at) - ms(b.armed_at));
  for (const t of active) { cache[t.symbol] ||= await loadBars(t.symbol); await evaluate(t, cache[t.symbol], m5Cache); }

  const shadowQ = await db.from("poi_depth_shadow").select("*").in("status", ["waiting", "open"]).order("frozen_at", { ascending: true }).limit(2000);
  if (shadowQ.error) throw new Error(shadowQ.error.message);
  for (const s of shadowQ.data || []) {
    const parent = byKey.get(s.trade_key); if (!parent) continue;
    cache[s.symbol] ||= await loadBars(s.symbol);
    await evaluateShadow(s, parent, cache[s.symbol], m5Cache);
  }

  const refreshedQ = await db.from("paper_trades").select("*").in("symbol", SYMBOLS).order("armed_at", { ascending: false }).limit(100);
  if (refreshedQ.error) throw new Error(refreshedQ.error.message);
  await applyFocusSemantics(refreshedQ.data || []);
  return { currentStates: (current.data || []).length, recoveredStage6Rows: (hist.data || []).length, evaluated: active.length, depthShadowsEvaluated: (shadowQ.data || []).length };
}

function depthAggregate(rows) {
  const out = [];
  for (const depthPct of DEPTH_PCTS) {
    const all = rows.filter(r => Number(r.depth_pct) === depthPct && r.prospective && r.eligible);
    const closed = all.filter(r => ["win", "loss", "timeout", "ambiguous", "not_filled"].includes(r.status));
    const scored = closed.filter(r => ["win", "loss", "timeout", "not_filled"].includes(r.status));
    const wins = scored.filter(r => r.status === "win").length, losses = scored.filter(r => r.status === "loss").length;
    const meanR = scored.length ? scored.reduce((s, r) => s + Number(r.gross_r || 0), 0) / scored.length : null;
    out.push({ depthPct, frozen: all.length, closed: closed.length, scored: scored.length, ambiguous: closed.filter(r => r.status === "ambiguous").length, wins, losses, fillCount: all.filter(r => r.filled_at).length, meanR: scored.length >= 30 ? meanR : null, performanceVisible: scored.length >= 30, evidenceReady: scored.length >= 100 });
  }
  return out;
}

async function snapshot(symbols, withBars) {
  const q = await db.from("paper_trades").select("*").in("symbol", symbols).order("armed_at", { ascending: false }).limit(50);
  if (q.error) throw new Error(q.error.message);
  const trades = q.data || [], keys = trades.map(t => t.trade_key);
  let events = [];
  if (keys.length) { const e = await db.from("paper_trade_events").select("*").in("trade_key", keys).order("event_at", { ascending: false }).limit(120); if (e.error) throw new Error(e.error.message); events = e.data || []; }
  const shadowQ = await db.from("poi_depth_shadow").select("trade_key,symbol,depth_pct,prospective,eligible,status,filled_at,exit_at,gross_r").in("symbol", symbols).order("updated_at", { ascending: false }).limit(2000);
  if (shadowQ.error) throw new Error(shadowQ.error.message);
  const shadowRows = shadowQ.data || [], summary = {};
  for (const s of symbols) {
    const x = trades.filter(t => t.symbol === s);
    summary[s] = { total: x.length, armed: x.filter(t => t.status === "armed").length, focusArmed: x.filter(t => t.status === "armed" && t.focus_active).length, researchWatch: x.filter(t => t.status === "armed" && !t.focus_active).length, open: x.filter(t => t.status === "open").length, closed: x.filter(t => ["win", "loss", "timeout", "ambiguous"].includes(t.status)).length, wins: x.filter(t => t.status === "win").length, losses: x.filter(t => t.status === "loss").length, latest: x[0] || null };
  }
  const chartBars = {};
  if (withBars) for (const s of symbols) chartBars[s] = await loadBars(s, 220);
  const prospectiveRows = shadowRows.filter(r => r.prospective), backfilledRows = shadowRows.filter(r => !r.prospective);
  return { summary, trades, events, chartBars, depthLearning: { baselineDepthPct: 50, productionRuleChanged: false, historicalM5: { decision: "KEEP_MIDPOINT_RESEARCH_ONLY", pooledBestDepthPct: 40, pooledBestOpportunityR: 0.1013882003, midpointOpportunityR: 0.0712918660, walkforwardDeltaR: -0.0352822581, walkforward95: [-0.1103956653, 0.0388482863] }, prospectiveStart: V20_PROSPECTIVE_START, prospectiveRows: prospectiveRows.length, backfilledRows: backfilledRows.length, byDepth: depthAggregate(shadowRows), suppression: "No depth performance is shown before 30 scored prospective rows; no automatic promotion occurs." } };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "GET") return reply({ error: "GET only" }, 405);
  try {
    const u = new globalThis.URL(req.url), requested = (u.searchParams.get("symbol") || SYMBOLS.join(",")).split(",").map(x => x.toUpperCase()).filter(x => SYMBOLS.includes(x)), symbols = requested.length ? requested : SYMBOLS;
    const run = u.searchParams.get("run") === "1" ? await runEngine() : null;
    const snap = await snapshot(symbols, u.searchParams.get("bars") === "1");
    return reply({ version: "V2 paper-trade engine v2.0", research_only: true, broker_execution: false, generated_at: new Date().toISOString(), run, ...snap, methodology: { entry: "50% live POI midpoint remains the only baseline paper-plan entry", timeInvalidation: "None for the baseline plan. Elapsed time changes lifecycle/evidence state but does not cancel an untouched POI.", waitingLifecycle: { freshThroughBars: ORIGINAL_WINDOW_BARS, extendedThroughBars: EXTENDED_WINDOW_BARS, studiedTailThroughBars: RESEARCH_TAIL_BARS, beyondTail: "continue research tracking, suppress from Focus" }, poiPenetration: "0=proximal edge, 0.5=midpoint, 1=distal edge. Exact penetration is tracked with tolerant boundary comparisons.", focusSemantics: "A newer same-symbol same-direction plan can supersede an older unfilled plan for Focus without deleting its research tracking.", depthShadow: { grid: "0%-100% in 5% steps", entryWaitBars: SHADOW_ENTRY_HORIZON_BARS, postEntryHoldBars: MAX_HOLD_BARS, baselineDepthPct: 50, automaticPromotion: false, backfillExcludedFromPromotion: true }, shallowPoiTouch: "Tracked as lifecycle/penetration evidence; not automatic cancellation.", preEntryTargetExtension: "Tracked as context; not a universal invalidation rule.", stop: "sweep extreme +/- 0.03 ATR", targetR: REWARD_R, maxHoldBars: MAX_HOLD_BARS, riskAtrGate: [MIN_RISK_ATR, MAX_RISK_ATR], historyRecoveryHours: HISTORY_RECOVERY_HOURS, triggerData: "same-source completed M15 structural bars only", sameBarPolicy: "public 5m when needed; otherwise ambiguous", executionTruth: "Research paper trades only; no broker bid/ask, spread, slippage or executable fill feed." } });
  } catch (e) { return reply({ error: String(e) }, 500); }
});
