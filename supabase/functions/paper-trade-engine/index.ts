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
const MAX_HOLD_BARS = 48;
const STOP_BUFFER_ATR = 0.03;
const REWARD_R = 2.5;
const MIN_RISK_ATR = 0.08;
const MAX_RISK_ATR = 1.60;
const HISTORY_RECOVERY_HOURS = 6;

const reply = (x, status = 200) => new Response(JSON.stringify(x), { status, headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" } });
const number = (v) => v === null || v === undefined || v === "" ? null : (Number.isFinite(Number(v)) ? Number(v) : null);
const ms = (t) => new Date(t).getTime();
const touch = (b, p) => b.low <= p && p <= b.high;
const zoneTouch = (b, lo, hi) => b.low <= hi && b.high >= lo;
const floor15 = (t) => new Date(Math.floor(ms(t) / 900000) * 900000).toISOString();
const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

function trueRanges(bars) {
  return bars.map((b, i) => i === 0 ? b.high - b.low : Math.max(b.high - b.low, Math.abs(b.high - bars[i - 1].close), Math.abs(b.low - bars[i - 1].close)));
}
function rollingMean(xs, n) {
  let sum = 0;
  return xs.map((x, i) => { sum += x; if (i >= n) sum -= xs[i - n]; return sum / Math.min(i + 1, n); });
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
      const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0 V2PaperResearch/1.4", "Accept": "application/json" } });
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
    context: { formation_stage: c.stage, formation_code: c.code, market_session: c.session, regime: c.regime, trends: c.trends, diagnostics: c.diagnostics, recovered_from_history: c.recovered, recovered_as_of: c.recovered ? c.sourceAt : null, entry_rule: "first future completed M15 bar after BOS touching POI midpoint; no time-only invalidation", v14_waiting_research: true, invalid_reason: valid ? null : `risk_atr ${riskAtr.toFixed(3)} outside ${MIN_RISK_ATR}-${MAX_RISK_ATR}` },
  };
  const w = await db.from("paper_trades").insert(row);
  if (w.error) throw new Error(`arm ${tradeKey}: ${w.error.message}`);
  await eventOnce(tradeKey, valid ? "armed" : "invalid", now, valid ? entry : null, { entry, stop, target, riskAtr, poiLow: low, poiHigh: high, recoveredFromHistory: c.recovered });
}

function hits(t, b) {
  return { entry: touch(b, Number(t.entry_price)), stop: t.direction === "long" ? b.low <= Number(t.stop_price) : b.high >= Number(t.stop_price), target: t.direction === "long" ? b.high >= Number(t.target_price) : b.low <= Number(t.target_price) };
}

async function resolve5m(t, bar, needsEntry) {
  let rows;
  try { rows = await load5m(t.symbol); } catch { return { kind: "ambiguous", reason: "5m public path unavailable" }; }
  const start = ms(bar.ts), sub = rows.filter(x => ms(x.ts) >= start && ms(x.ts) < start + 900000);
  if (!sub.length) return { kind: "ambiguous", reason: "no completed 5m path" };
  let entered = !needsEntry, entryAt = needsEntry ? null : t.entry_at;
  for (const b of sub) {
    const h = hits(t, b);
    if (!entered) {
      if (!h.entry) continue;
      if (h.stop || h.target) return { kind: "ambiguous", reason: "entry and exit level touched in same 5m bar" };
      entered = true; entryAt = b.ts; continue;
    }
    if (h.stop && h.target) return { kind: "ambiguous", reason: "SL and TP touched in same 5m bar", entryAt };
    if (h.stop) return { kind: "loss", entryAt, exitAt: b.ts, exitPrice: Number(t.stop_price) };
    if (h.target) return { kind: "win", entryAt, exitAt: b.ts, exitPrice: Number(t.target_price) };
  }
  return entered ? { kind: "open", entryAt: entryAt || bar.ts } : { kind: "ambiguous", reason: "M15 entry touch not reproduced by 5m path" };
}

function excursions(t, bars, entryIdx, exitIdx) {
  const xs = bars.slice(entryIdx, exitIdx + 1), entry = Number(t.entry_price), risk = Number(t.risk_distance);
  if (!xs.length || risk <= 0) return { mfe: null, mae: null };
  const hi = Math.max(...xs.map(x => x.high)), lo = Math.min(...xs.map(x => x.low));
  return t.direction === "long" ? { mfe: (hi - entry) / risk, mae: (entry - lo) / risk } : { mfe: (entry - lo) / risk, mae: (hi - entry) / risk };
}

async function finish(t, status, at, price, bars, entryIdx, exitIdx, resolution = "15m", reason = null) {
  const ex = excursions(t, bars, entryIdx, exitIdx), gross = status === "win" ? REWARD_R : status === "loss" ? -1 : null;
  const w = await db.from("paper_trades").update({ status, lifecycle_phase: "closed", exit_at: at, exit_price: price, gross_r: gross, bars_held: exitIdx - entryIdx + 1, mfe_r: ex.mfe, mae_r: ex.mae, resolution_timeframe: resolution, ambiguous_reason: reason, updated_at: new Date().toISOString() }).eq("trade_key", t.trade_key);
  if (w.error) throw new Error(`finish ${t.trade_key}: ${w.error.message}`);
  await eventOnce(t.trade_key, status, at, price, { grossR: gross, mfeR: ex.mfe, maeR: ex.mae, resolution, reason });
}

function waitingMetrics(t, bars, bosIdx) {
  const seq = bars.slice(bosIdx + 1), entry = Number(t.entry_price), lo = Number(t.poi_low), hi = Number(t.poi_high), risk = Number(t.risk_distance);
  const fillIdx = seq.findIndex(b => touch(b, entry)), zoneIdx = seq.findIndex(b => zoneTouch(b, lo, hi));
  const pre = fillIdx >= 0 ? seq.slice(0, fillIdx) : seq;
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
  return { seq, fillIdx, zoneIdx, age, favorableR, targetReached, shallow, condition, phase };
}

async function updateWaiting(t, m) {
  const firstZone = m.zoneIdx >= 0 ? m.seq[m.zoneIdx]?.ts : null;
  const context = { ...(t.context || {}), v14_waiting_research: true, v14_reactivation_pending: false, time_only_invalidation: false, old_8_bar_window_passed: m.age > ORIGINAL_WINDOW_BARS, waiting_evidence: m.phase === "outside_studied_tail" ? "outside studied 48h tail" : "within studied public-proxy tail" };
  const patch = { status: "armed", entry_expires_at: null, lifecycle_phase: m.phase, pending_age_bars: m.age, first_zone_touch_at: t.first_zone_touch_at || firstZone, first_zone_touch_bar: t.first_zone_touch_bar || (m.zoneIdx >= 0 ? m.zoneIdx + 1 : null), pre_entry_max_favorable_r: m.favorableR, pre_entry_target_reached: m.targetReached, setup_condition: m.condition, research_tail_bars: RESEARCH_TAIL_BARS, context, updated_at: new Date().toISOString() };
  const w = await db.from("paper_trades").update(patch).eq("trade_key", t.trade_key);
  if (w.error) throw new Error(`waiting ${t.trade_key}: ${w.error.message}`);
  const at = m.seq.at(-1)?.ts || new Date().toISOString();
  if (t.status === "expired" || t.context?.v14_reactivation_pending) await eventOnce(t.trade_key, "reactivated_v14", at, null, { reason: "8-bar expiry removed after waiting-time study" });
  if (m.phase !== (t.lifecycle_phase || "fresh_wait")) await eventOnce(t.trade_key, m.phase, at, null, { ageBars: m.age });
  if (m.shallow && !t.first_zone_touch_at) await eventOnce(t.trade_key, "partially_mitigated", firstZone || at, null, { ageBars: m.zoneIdx + 1 });
  if (m.targetReached && !t.pre_entry_target_reached) await eventOnce(t.trade_key, "target_delivered_before_entry", at, Number(t.target_price), { preEntryMaxFavorableR: m.favorableR });
}

async function evaluate(t, bars) {
  const bosIdx = bars.findIndex(b => b.ts === new Date(t.bos_time).toISOString());
  if (bosIdx < 0) return;
  if (t.status === "armed" || t.status === "expired") {
    const m = waitingMetrics(t, bars, bosIdx);
    if (m.fillIdx < 0) { await updateWaiting(t, m); return; }
    const entryIdx = bosIdx + 1 + m.fillIdx, bar = bars[entryIdx], h = hits(t, bar), barsToEntry = entryIdx - bosIdx;
    const base = { status: "open", lifecycle_phase: "filled", entry_at: bar.ts, bars_to_entry: barsToEntry, pending_age_bars: barsToEntry, entry_expires_at: null, first_zone_touch_at: t.first_zone_touch_at || (m.zoneIdx >= 0 ? m.seq[m.zoneIdx]?.ts : null), first_zone_touch_bar: t.first_zone_touch_bar || (m.zoneIdx >= 0 ? m.zoneIdx + 1 : null), pre_entry_max_favorable_r: m.favorableR, pre_entry_target_reached: m.targetReached, setup_condition: m.condition, context: { ...(t.context || {}), v14_waiting_research: true, v14_reactivation_pending: false, time_only_invalidation: false, old_8_bar_window_passed: barsToEntry > ORIGINAL_WINDOW_BARS }, updated_at: new Date().toISOString() };
    if (h.stop || h.target) {
      const r = await resolve5m({ ...t, ...base }, bar, true);
      if (r.kind === "ambiguous") { await finish({ ...t, ...base }, "ambiguous", bar.ts, null, bars, entryIdx, entryIdx, "5m", r.reason); return; }
      const entryAt = r.entryAt || bar.ts, ctx = { ...base.context, entry_bar_resolved_5m: true };
      const w = await db.from("paper_trades").update({ ...base, status: r.kind === "open" ? "open" : r.kind, entry_at: entryAt, resolution_timeframe: "5m", context: ctx }).eq("trade_key", t.trade_key);
      if (w.error) throw new Error(w.error.message);
      await eventOnce(t.trade_key, "entry", entryAt, Number(t.entry_price), { barsToEntry, resolution: "5m", lifecyclePhase: m.phase, setupCondition: m.condition });
      if (r.kind === "win" || r.kind === "loss") await finish({ ...t, ...base, context: ctx }, r.kind, r.exitAt, r.exitPrice, bars, entryIdx, entryIdx, "5m");
      return;
    }
    const w = await db.from("paper_trades").update({ ...base, resolution_timeframe: "15m" }).eq("trade_key", t.trade_key);
    if (w.error) throw new Error(w.error.message);
    await eventOnce(t.trade_key, "entry", bar.ts, Number(t.entry_price), { barsToEntry, resolution: "15m", lifecyclePhase: m.phase, setupCondition: m.condition, timeSemantics: "M15 containing first midpoint touch" });
    return;
  }
  if (t.status !== "open" || !t.entry_at) return;
  const entryIdx = bars.findIndex(b => b.ts === floor15(t.entry_at));
  if (entryIdx < 0) return;
  const lastIdx = Math.min(bars.length - 1, entryIdx + MAX_HOLD_BARS), firstIdx = t.context?.entry_bar_resolved_5m ? entryIdx + 1 : entryIdx;
  for (let i = firstIdx; i <= lastIdx; i++) {
    const h = hits(t, bars[i]);
    if (h.stop && h.target) {
      const r = await resolve5m(t, bars[i], false);
      if (r.kind === "ambiguous") { await finish(t, "ambiguous", bars[i].ts, null, bars, entryIdx, i, "5m", r.reason); return; }
      await finish(t, r.kind, r.exitAt, r.exitPrice, bars, entryIdx, i, "5m"); return;
    }
    if (h.stop) { await finish(t, "loss", bars[i].ts, Number(t.stop_price), bars, entryIdx, i); return; }
    if (h.target) { await finish(t, "win", bars[i].ts, Number(t.target_price), bars, entryIdx, i); return; }
  }
  const ex = excursions(t, bars, entryIdx, lastIdx);
  if (bars.length - 1 >= entryIdx + MAX_HOLD_BARS) {
    const b = bars[entryIdx + MAX_HOLD_BARS], rawR = t.direction === "long" ? (b.close - Number(t.entry_price)) / Number(t.risk_distance) : (Number(t.entry_price) - b.close) / Number(t.risk_distance), gross = clamp(rawR, -1, REWARD_R);
    const w = await db.from("paper_trades").update({ status: "timeout", lifecycle_phase: "closed", exit_at: b.ts, exit_price: b.close, gross_r: gross, bars_held: MAX_HOLD_BARS + 1, mfe_r: ex.mfe, mae_r: ex.mae, resolution_timeframe: "15m", updated_at: new Date().toISOString() }).eq("trade_key", t.trade_key);
    if (w.error) throw new Error(w.error.message);
    await eventOnce(t.trade_key, "timeout", b.ts, b.close, { grossR: gross, mfeR: ex.mfe, maeR: ex.mae }); return;
  }
  await db.from("paper_trades").update({ mfe_r: ex.mfe, mae_r: ex.mae, bars_held: lastIdx - entryIdx + 1, updated_at: new Date().toISOString() }).eq("trade_key", t.trade_key);
}

async function runEngine() {
  const current = await db.from("market_states").select("*").in("symbol", SYMBOLS);
  if (current.error) throw new Error(current.error.message);
  const since = new Date(Date.now() - HISTORY_RECOVERY_HOURS * 3600000).toISOString();
  const hist = await db.from("market_state_history").select("symbol,as_of,formation_stage,formation_code,formation_direction,regime,state").in("symbol", SYMBOLS).gte("formation_stage", 6).gte("as_of", since).order("as_of", { ascending: false }).limit(180);
  if (hist.error) throw new Error(hist.error.message);
  const cache = {}, seen = new Set(), candidates = [...(current.data || []).map(currentCandidate), ...(hist.data || []).map(historyCandidate)];
  for (const c of candidates) {
    const sweep = c.form?.sweepTime, key = sweep ? `${c.symbol}:${c.direction}:${new Date(sweep).toISOString()}` : null;
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    cache[c.symbol] ||= await loadBars(c.symbol);
    await armCandidate(c, cache[c.symbol]);
  }
  const active = await db.from("paper_trades").select("*").in("status", ["armed", "expired", "open"]).order("armed_at", { ascending: true });
  if (active.error) throw new Error(active.error.message);
  for (const t of active.data || []) { cache[t.symbol] ||= await loadBars(t.symbol); await evaluate(t, cache[t.symbol]); }
  return { currentStates: (current.data || []).length, recoveredStage6Rows: (hist.data || []).length, evaluated: (active.data || []).length };
}

async function snapshot(symbols, withBars) {
  const q = await db.from("paper_trades").select("*").in("symbol", symbols).order("armed_at", { ascending: false }).limit(50);
  if (q.error) throw new Error(q.error.message);
  const trades = q.data || [], keys = trades.map(t => t.trade_key);
  let events = [];
  if (keys.length) { const e = await db.from("paper_trade_events").select("*").in("trade_key", keys).order("event_at", { ascending: false }).limit(120); if (e.error) throw new Error(e.error.message); events = e.data || []; }
  const summary = {};
  for (const s of symbols) {
    const x = trades.filter(t => t.symbol === s);
    summary[s] = { total: x.length, armed: x.filter(t => t.status === "armed").length, open: x.filter(t => t.status === "open").length, closed: x.filter(t => ["win", "loss", "timeout", "ambiguous"].includes(t.status)).length, wins: x.filter(t => t.status === "win").length, losses: x.filter(t => t.status === "loss").length, latest: x[0] || null };
  }
  const chartBars = {};
  if (withBars) for (const s of symbols) chartBars[s] = await loadBars(s, 220);
  return { summary, trades, events, chartBars };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "GET") return reply({ error: "GET only" }, 405);
  try {
    const u = new globalThis.URL(req.url), requested = (u.searchParams.get("symbol") || SYMBOLS.join(",")).split(",").map(x => x.toUpperCase()).filter(x => SYMBOLS.includes(x)), symbols = requested.length ? requested : SYMBOLS;
    const run = u.searchParams.get("run") === "1" ? await runEngine() : null;
    const snap = await snapshot(symbols, u.searchParams.get("bars") === "1");
    return reply({ version: "V2 paper-trade engine v1.4", research_only: true, broker_execution: false, generated_at: new Date().toISOString(), run, ...snap, methodology: { entry: "50% live POI midpoint after fresh BOS-confirmed POI", timeInvalidation: "None. Elapsed time changes lifecycle/evidence state but does not cancel an untouched POI.", waitingLifecycle: { freshThroughBars: ORIGINAL_WINDOW_BARS, extendedThroughBars: EXTENDED_WINDOW_BARS, studiedTailThroughBars: RESEARCH_TAIL_BARS, beyondTail: "continue tracking, label outside studied tail" }, shallowPoiTouch: "Tracked as partially mitigated/degraded context; not automatic cancellation.", preEntryTargetExtension: "Tracked as context; historical public proxy did not support universal cancellation.", stop: "sweep extreme +/- 0.03 ATR", targetR: REWARD_R, maxHoldBars: MAX_HOLD_BARS, riskAtrGate: [MIN_RISK_ATR, MAX_RISK_ATR], historyRecoveryHours: HISTORY_RECOVERY_HOURS, triggerData: "same-source completed M15 structural bars only", sameBarPolicy: "public 5m when needed; otherwise ambiguous", executionTruth: "Research paper trades only; no broker bid/ask, spread, slippage or executable fill feed." } });
  } catch (e) { return reply({ error: String(e) }, 500); }
});