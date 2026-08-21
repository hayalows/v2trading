import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });

async function cronOk(req: Request) {
  const k = req.headers.get("x-v2-cron-key") ?? "";
  if (!k) return false;
  const q = await db.from("v2_runtime_secrets").select("secret").eq("name", "cron").maybeSingle();
  if (q.error || !q.data?.secret) return false;
  const a = new TextEncoder().encode(k), b = new TextEncoder().encode(String(q.data.secret));
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a[i]! ^ b[i]!;
  return d === 0;
}

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Cache-Control": "no-store",
};

const INSTRUMENTS: Record<string, { name: string; chart: string }> = {
  EURUSD: { name: "Euro / U.S. Dollar", chart: "EURUSD=X" },
  GBPUSD: { name: "British Pound / U.S. Dollar", chart: "GBPUSD=X" },
};

type Bar = { ts: string; open: number; high: number; low: number; close: number; volume: number | null };
type TrendResult = {
  label: "bullish" | "bearish" | "mixed" | "insufficient";
  strength: number;
  score: number;
  ema20: number | null;
  ema50: number | null;
  efficiency: number;
  volPercentile: number;
  normalizedAtr: number;
};

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" },
  });
}
function finite(x: unknown): number | null { const n = Number(x); return Number.isFinite(n) ? n : null; }
function clamp(v: number, lo: number, hi: number) { return Math.max(lo, Math.min(hi, v)); }
function mean(xs: number[]) { return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN; }
function median(xs: number[]) { if (!xs.length) return NaN; const x = [...xs].sort((a, b) => a - b), m = Math.floor(x.length / 2); return x.length % 2 ? x[m] : (x[m - 1] + x[m]) / 2; }
function std(xs: number[]) { if (xs.length < 2) return 0; const m = mean(xs); return Math.sqrt(mean(xs.map(x => (x - m) ** 2))); }
function percentileRank(xs: number[], x: number) { if (!xs.length || !Number.isFinite(x)) return 0; return 100 * xs.filter(v => v <= x).length / xs.length; }
function ema(values: number[], period: number) { if (!values.length) return []; const k = 2 / (period + 1), out = [values[0]]; for (let i = 1; i < values.length; i++) out.push(values[i] * k + out[i - 1] * (1 - k)); return out; }
function tr(bars: Bar[]) { return bars.map((b, i) => i === 0 ? b.high - b.low : Math.max(b.high - b.low, Math.abs(b.high - bars[i - 1].close), Math.abs(b.low - bars[i - 1].close))); }
function rollingMean(values: number[], n: number) { const out: number[] = []; let sum = 0; for (let i = 0; i < values.length; i++) { sum += values[i]; if (i >= n) sum -= values[i - n]; out.push(sum / Math.min(i + 1, n)); } return out; }
function logReturns(bars: Bar[]) { const out: number[] = []; for (let i = 1; i < bars.length; i++) out.push(Math.log(bars[i].close / bars[i - 1].close)); return out; }
function efficiencyRatio(closes: number[], n = 20) { if (closes.length <= n) return 0; const end = closes.length - 1, start = end - n, change = Math.abs(closes[end] - closes[start]); let path = 0; for (let i = start + 1; i <= end; i++) path += Math.abs(closes[i] - closes[i - 1]); return path > 0 ? clamp(change / path, 0, 1) : 0; }

function cleanCompleted(bars: Bar[], seconds: number) {
  let out = bars.filter(b => b.open > 0 && b.high > 0 && b.low > 0 && b.close > 0 && b.high >= b.low);
  while (out.length > 1) {
    const start = new Date(out.at(-1)!.ts).getTime();
    if (Date.now() < start + seconds * 1000) out = out.slice(0, -1); else break;
  }
  return out;
}
function aggregate(bars: Bar[], hours: number) {
  const ms = hours * 3600_000, groups = new Map<number, Bar[]>();
  for (const b of bars) { const key = Math.floor(new Date(b.ts).getTime() / ms) * ms, g = groups.get(key) ?? []; g.push(b); groups.set(key, g); }
  return [...groups.entries()].sort((a, b) => a[0] - b[0]).map(([t, g]) => ({ ts: new Date(t).toISOString(), open: g[0].open, high: Math.max(...g.map(x => x.high)), low: Math.min(...g.map(x => x.low)), close: g.at(-1)!.close, volume: g.some(x => x.volume != null) ? g.reduce((s, x) => s + (x.volume ?? 0), 0) : null }));
}

async function yahoo(symbol: string, interval: string, range: string) {
  const encoded = encodeURIComponent(symbol); let last = "";
  for (const host of ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]) {
    try {
      const url = `https://${host}/v8/finance/chart/${encoded}?interval=${interval}&range=${range}&includePrePost=false&events=div%2Csplits`;
      const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0 V2QuantResearch/4.0", "Accept": "application/json" } });
      if (!r.ok) { last = `${host}:${r.status}`; continue; }
      const j = await r.json(), root = j?.chart?.result?.[0];
      if (!root?.timestamp?.length) { last = `${host}:empty`; continue; }
      const q = root.indicators?.quote?.[0] ?? {}, bars: Bar[] = [];
      for (let i = 0; i < root.timestamp.length; i++) {
        const o = finite(q.open?.[i]), h = finite(q.high?.[i]), l = finite(q.low?.[i]), c = finite(q.close?.[i]);
        if (o == null || h == null || l == null || c == null || o <= 0 || h <= 0 || l <= 0 || c <= 0 || h < l) continue;
        bars.push({ ts: new Date(root.timestamp[i] * 1000).toISOString(), open: o, high: h, low: l, close: c, volume: finite(q.volume?.[i]) });
      }
      return { bars, meta: root.meta ?? {}, source: "Yahoo Finance public chart" };
    } catch (e) { last = String(e); }
  }
  throw new Error(`chart fetch failed ${last}`);
}

async function cached(key: string, ttlMs: number, loader: () => Promise<any>) {
  const read = await db.from("provider_cache").select("payload,fetched_at,expires_at,status").eq("cache_key", key).maybeSingle();
  const old = read.data;
  if (old && new Date(old.expires_at).getTime() > Date.now()) return { payload: old.payload, fetchedAt: old.fetched_at, status: old.status };
  try {
    const payload = await loader(), now = new Date(), expires = new Date(now.getTime() + ttlMs);
    const w = await db.from("provider_cache").upsert({ cache_key: key, payload, fetched_at: now.toISOString(), expires_at: expires.toISOString(), status: "ok", error: null });
    if (w.error) throw new Error(w.error.message);
    return { payload, fetchedAt: now.toISOString(), status: "ok" };
  } catch (e) {
    if (old) return { payload: old.payload, fetchedAt: old.fetched_at, status: "stale", error: String(e) };
    return { payload: null, fetchedAt: new Date(0).toISOString(), status: "error", error: String(e) };
  }
}
async function fxReference() {
  return cached("exchangerate-dev-usd", 300_000, async () => {
    const r = await fetch("https://api.exchangerate.dev/v1/latest/USD?symbols=EUR,GBP", { headers: { "Accept": "application/json", "User-Agent": "V2QuantResearchLab/4.0" } });
    if (!r.ok) throw new Error(`exchangerate.dev ${r.status}`);
    const j = await r.json();
    if (j?.result !== "success" || !j?.rates?.EUR || !j?.rates?.GBP) throw new Error("invalid FX reference response");
    return j;
  });
}

function trend(bars: Bar[]): TrendResult {
  if (bars.length < 60) return { label: "insufficient", strength: 0, score: 0, ema20: null, ema50: null, efficiency: 0, volPercentile: 0, normalizedAtr: 0 };
  const closes = bars.map(x => x.close), e20 = ema(closes, 20), e50 = ema(closes, 50), atr = rollingMean(tr(bars), 14), i = bars.length - 1;
  const a = Math.max(atr[i], Math.abs(closes[i]) * 1e-6);
  const p1 = clamp((closes[i] - e20[i]) / a, -3, 3), p2 = clamp((e20[i] - e50[i]) / a, -3, 3), p3 = clamp((e20[i] - e20[Math.max(0, i - 5)]) / a, -3, 3);
  const score = p1 * .50 + p2 * .72 + p3 * .48;
  const label: TrendResult["label"] = score > .35 ? "bullish" : score < -.35 ? "bearish" : "mixed";
  const efficiency = efficiencyRatio(closes, 20);
  const normalized = atr.map((x, k) => x / Math.max(Math.abs(closes[k]), 1e-9));
  const hist = normalized.slice(Math.max(0, normalized.length - 120));
  const volPercentile = percentileRank(hist, normalized[i]);
  const strength = Math.round(clamp((Math.abs(score) / 2.6) * 72 + efficiency * 28, 0, 100));
  return { label, strength, score, ema20: e20[i], ema50: e50[i], efficiency, volPercentile, normalizedAtr: normalized[i] };
}

function swings(bars: Bar[]) {
  const highs: any[] = [], lows: any[] = [];
  for (let i = 2; i < bars.length - 2; i++) {
    if (bars[i].high > bars[i - 1].high && bars[i].high >= bars[i - 2].high && bars[i].high > bars[i + 1].high && bars[i].high >= bars[i + 2].high) highs.push({ i, price: bars[i].high, ts: bars[i].ts });
    if (bars[i].low < bars[i - 1].low && bars[i].low <= bars[i - 2].low && bars[i].low < bars[i + 1].low && bars[i].low <= bars[i + 2].low) lows.push({ i, price: bars[i].low, ts: bars[i].ts });
  }
  return { lastHigh: highs.at(-1) ?? null, lastLow: lows.at(-1) ?? null };
}
function session() {
  const h = new Date().getUTCHours(), london = h >= 7 && h < 16, ny = h >= 13 && h < 22, asia = h >= 0 && h < 9;
  if (london && ny) return "London / New York overlap"; if (london) return "London"; if (ny) return "New York"; if (asia) return "Asia"; return "Transition / off-hours";
}

function formation(bars: Bar[], structurePrice: number) {
  if (bars.length < 45) return { stage: 0, code: "NO_SETUP", label: "Not enough M15 history", direction: null, maturity: 0, poiHigh: null, poiLow: null, distancePoiAtr: null, details: {} };
  const atr = rollingMean(tr(bars), 14), n = bars.length, a = Math.max(atr.at(-1)!, Math.abs(bars.at(-1)!.close) * 1e-6); let sweep: any = null;
  for (let i = Math.max(22, n - 12); i < n; i++) {
    const prior = bars.slice(i - 20, i), ph = Math.max(...prior.map(x => x.high)), pl = Math.min(...prior.map(x => x.low)), ai = Math.max(atr[i], a);
    const bear = bars[i].high > ph + .03 * ai && bars[i].close < ph, bull = bars[i].low < pl - .03 * ai && bars[i].close > pl;
    if (bear || bull) sweep = { i, direction: bear ? "short" : "long", ts: bars[i].ts };
  }
  const sw = swings(bars.slice(-60));
  if (!sweep) {
    const hi = sw.lastHigh?.price ?? Math.max(...bars.slice(-20).map(x => x.high)), lo = sw.lastLow?.price ?? Math.min(...bars.slice(-20).map(x => x.low));
    const dh = Math.abs(structurePrice - hi) / a, dl = Math.abs(structurePrice - lo) / a;
    if (Math.min(dh, dl) <= .35) { const dir = dl < dh ? "long" : "short"; return { stage: 1, code: "LIQUIDITY_NEARBY", label: `Price is near ${dl < dh ? "sell-side" : "buy-side"} liquidity`, direction: dir, maturity: 30, poiHigh: null, poiLow: null, distancePoiAtr: null, details: { distanceHighAtr: dh, distanceLowAtr: dl } }; }
    return { stage: 0, code: "NO_SETUP", label: "No active V2 formation", direction: null, maturity: 10, poiHigh: null, poiLow: null, distancePoiAtr: null, details: { distanceHighAtr: dh, distanceLowAtr: dl } };
  }
  const pre = bars.slice(Math.max(0, sweep.i - 8), sweep.i), bosHigh = Math.max(...pre.map(x => x.high)), bosLow = Math.min(...pre.map(x => x.low)); let bos = -1;
  for (let i = sweep.i + 1; i < n; i++) if ((sweep.direction === "long" && bars[i].close > bosHigh) || (sweep.direction === "short" && bars[i].close < bosLow)) { bos = i; break; }
  if (bos < 0) { const age = n - 1 - sweep.i; return { stage: age >= 1 ? 4 : 3, code: age >= 1 ? "WAITING_FOR_BOS" : "SWEEP_CONFIRMED", label: age >= 1 ? "Liquidity sweep confirmed; waiting for BOS" : "Liquidity sweep confirmed", direction: sweep.direction, maturity: age >= 1 ? 50 : 42, poiHigh: null, poiLow: null, distancePoiAtr: null, details: { sweepTime: sweep.ts, bosReference: sweep.direction === "long" ? bosHigh : bosLow } }; }
  let poi = -1; for (let i = bos; i >= sweep.i; i--) { const opposite = sweep.direction === "long" ? bars[i].close < bars[i].open : bars[i].close > bars[i].open; if (opposite) { poi = i; break; } }
  if (poi < 0) return { stage: 5, code: "BOS_CONFIRMED", label: "BOS confirmed; no clean POI identified", direction: sweep.direction, maturity: 60, poiHigh: null, poiLow: null, distancePoiAtr: null, details: { sweepTime: sweep.ts, bosTime: bars[bos].ts } };
  const pHigh = bars[poi].high, pLow = bars[poi].low, mid = (pHigh + pLow) / 2, dist = Math.abs(structurePrice - mid) / a, inside = structurePrice >= pLow && structurePrice <= pHigh; let touched = false;
  for (let i = bos + 1; i < n - 1; i++) if (bars[i].low <= pHigh && bars[i].high >= pLow) { touched = true; break; }
  if (touched && !inside) return { stage: 2, code: "POI_USED", label: "Recent V2 sequence found, but the POI has already been revisited", direction: sweep.direction, maturity: 25, poiHigh: pHigh, poiLow: pLow, distancePoiAtr: dist, details: { sweepTime: sweep.ts, bosTime: bars[bos].ts, poiTime: bars[poi].ts, fresh: false } };
  if (inside) return { stage: 8, code: "ENTRY_ZONE_REACHED", label: "Research entry zone reached — not a trade signal", direction: sweep.direction, maturity: 90, poiHigh: pHigh, poiLow: pLow, distancePoiAtr: dist, details: { sweepTime: sweep.ts, bosTime: bars[bos].ts, poiTime: bars[poi].ts, fresh: !touched } };
  if (dist <= .5) return { stage: 7, code: "APPROACHING_POI", label: "Fresh POI identified; price is approaching the zone", direction: sweep.direction, maturity: 80, poiHigh: pHigh, poiLow: pLow, distancePoiAtr: dist, details: { sweepTime: sweep.ts, bosTime: bars[bos].ts, poiTime: bars[poi].ts, fresh: !touched } };
  return { stage: 6, code: "FRESH_POI_IDENTIFIED", label: "BOS confirmed and a fresh POI is identified", direction: sweep.direction, maturity: 70, poiHigh: pHigh, poiLow: pLow, distancePoiAtr: dist, details: { sweepTime: sweep.ts, bosTime: bars[bos].ts, poiTime: bars[poi].ts, fresh: !touched } };
}

function regime(h4: Bar[], m15: Bar[], h4t: TrendResult, m15t: TrendResult) {
  const tr15 = tr(m15), fast = mean(tr15.slice(-8)), slow = median(tr15.slice(-50));
  const volShock = slow > 0 ? fast / slow : 1;
  if (m15t.volPercentile >= 82 || volShock >= 1.45) return "volatility expansion";
  if (m15t.volPercentile <= 18 && volShock <= .75) return "volatility compression";
  if (h4t.efficiency >= .38 && h4t.label !== "mixed") return "directional trend";
  if (h4t.efficiency <= .20 && Math.abs(h4t.score) < .75) return "range / mean-reverting";
  return "transition";
}

function contextDiagnostics(trends: Record<string, TrendResult>, m15: Bar[], form: any) {
  const weight: Record<string, number> = { d1: 3, h4: 3, h1: 2, m15: 1 };
  let signed = 0, activeWeight = 0;
  for (const tf of ["d1", "h4", "h1", "m15"]) {
    const t = trends[tf], w = weight[tf];
    if (t.label === "bullish") { signed += w; activeWeight += w; }
    else if (t.label === "bearish") { signed -= w; activeWeight += w; }
  }
  const alignment = activeWeight ? Math.round(100 * Math.abs(signed) / activeWeight) : 0;
  const dominant = signed >= 3 ? "bullish" : signed <= -3 ? "bearish" : "mixed";
  const expected = form.direction === "long" ? "bullish" : form.direction === "short" ? "bearish" : null;
  let structureContext = "neutral";
  if (expected) structureContext = dominant === expected && alignment >= 55 ? "supportive" : dominant !== "mixed" && dominant !== expected && alignment >= 55 ? "conflicting" : "mixed";

  const returns = logReturns(m15), recentVol = std(returns.slice(-8)), baselineVol = std(returns.slice(-50));
  const volShock = baselineVol > 0 ? recentVol / baselineVol : 1;
  const eightBarMove = m15.length > 8 ? Math.abs(Math.log(m15.at(-1)!.close / m15.at(-9)!.close)) : 0;
  const expectedMove = baselineVol > 0 ? baselineVol * Math.sqrt(8) : 1e-9;
  const returnShock = eightBarMove / expectedMove;
  const shiftScore = Math.round(clamp(((Math.max(0, volShock - 1) / .8) * .55 + (Math.max(0, returnShock - 1) / 2) * .45) * 100, 0, 100));
  const shiftRisk = shiftScore >= 70 ? "high" : shiftScore >= 40 ? "elevated" : "stable";
  return { alignmentPct: alignment, dominantDirection: dominant, structureContext, shiftRisk, shiftScore, volShock, returnShock };
}

function barQuality(bars: Bar[], intervalMinutes: number) {
  const recent = bars.slice(-96), times = recent.map(b => new Date(b.ts).getTime()); let gaps = 0, duplicates = 0;
  for (let i = 1; i < times.length; i++) { const d = (times[i] - times[i - 1]) / 60_000; if (d === 0) duplicates++; else if (d > intervalMinutes * 1.5 && d < 24 * 60) gaps++; }
  const lastStart = times.at(-1) ?? 0, now = Date.now(), step = intervalMinutes * 60_000;
  const expectedStart = Math.floor(now / step) * step - step;
  const lagBars = lastStart ? Math.max(0, Math.round((expectedStart - lastStart) / step)) : 999;
  const freshness = lagBars === 0 ? "current completed candle" : lagBars === 1 ? "one bar behind" : "stale";
  return { gaps, duplicates, lagBars, freshness, expectedLastCompletedStart: new Date(expectedStart).toISOString(), lastBarStart: lastStart ? new Date(lastStart).toISOString() : null };
}

async function prospectiveAnalytics(symbol: string) {
  const q = await db.from("market_state_history").select("as_of,formation_stage,formation_code,formation_direction,regime,state").eq("symbol", symbol).order("as_of", { ascending: true }).limit(300);
  const rows = q.data ?? [];
  if (!rows.length) return { observations: 0, sampleStatus: "collecting", transitions: 0, stage5Events: 0, stage6Events: 0, recentPath: [], regimeChanges: 0, trendChanges: 0, note: "No prospective observations yet." };
  let transitions = 0, stage5Events = 0, stage6Events = 0, regimeChanges = 0, trendChanges = 0;
  for (let i = 1; i < rows.length; i++) {
    if (rows[i].formation_stage !== rows[i - 1].formation_stage || rows[i].formation_direction !== rows[i - 1].formation_direction) transitions++;
    if ((rows[i - 1].formation_stage ?? 0) < 5 && (rows[i].formation_stage ?? 0) >= 5) stage5Events++;
    if ((rows[i - 1].formation_stage ?? 0) < 6 && (rows[i].formation_stage ?? 0) >= 6) stage6Events++;
    if (rows[i].regime !== rows[i - 1].regime) regimeChanges++;
    const a = rows[i - 1].state?.trends?.h4?.label, b = rows[i].state?.trends?.h4?.label; if (a && b && a !== b) trendChanges++;
  }
  const status = rows.length < 30 ? "early sample" : rows.length < 100 ? "building sample" : "research sample";
  return {
    observations: rows.length,
    firstSeen: rows[0].as_of,
    lastSeen: rows.at(-1)?.as_of,
    sampleStatus: status,
    transitions,
    stage5Events,
    stage6Events,
    regimeChanges,
    trendChanges,
    recentPath: rows.slice(-8).map(r => ({ asOf: r.as_of, stage: r.formation_stage, code: r.formation_code, direction: r.formation_direction, regime: r.regime })),
    note: rows.length < 100 ? "Prospective sample is still too small for win-rate claims. It is shown for monitoring, not inference." : "Prospective sample is large enough for descriptive transition analysis; profitability still requires execution-safe labels.",
  };
}

async function persistBars(symbol: string, tf: string, bars: Bar[], source: string) {
  const q = await db.from("market_bars").select("*", { count: "exact", head: true }).eq("symbol", symbol).eq("timeframe", tf), initial = (q.count ?? 0) === 0;
  const keep = initial ? (tf === "15m" ? 500 : tf === "1d" ? 220 : 180) : 8;
  const rows = bars.slice(-keep).map(b => ({ symbol, timeframe: tf, ts: b.ts, open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume, source, is_proxy: false }));
  if (rows.length) { const w = await db.from("market_bars").upsert(rows, { onConflict: "symbol,timeframe,ts,source" }); if (w.error) throw new Error(`bars ${symbol}/${tf}: ${w.error.message}`); }
}

function summaryText(symbol: string, trends: Record<string, TrendResult>, reg: string, form: any, diag: any) {
  const htf = trends.d1.label === trends.h4.label && trends.d1.label !== "mixed" ? `${trends.d1.label} D1/H4 alignment` : `D1 ${trends.d1.label}, H4 ${trends.h4.label}`;
  const formation = form.stage >= 5 ? `Structure is mature enough for chart review: ${form.label}.` : form.stage >= 3 ? `The pair is on the watchlist: ${form.label}.` : form.label;
  const context = form.direction ? ` Context is ${diag.structureContext} for the ${form.direction} sequence.` : "";
  return `${symbol}: ${htf}. Regime: ${reg}. ${formation}${context} Regime-shift risk is ${diag.shiftRisk}.`;
}

async function refresh(symbol: string) {
  const cfg = INSTRUMENTS[symbol]; if (!cfg) throw new Error("unknown symbol");
  const [m15r, h1r, d1r, fx] = await Promise.all([
    yahoo(cfg.chart, "15m", "1mo"), yahoo(cfg.chart, "1h", "3mo"), yahoo(cfg.chart, "1d", "1y"), fxReference(),
  ]);
  const m15 = cleanCompleted(m15r.bars, 900), h1 = cleanCompleted(h1r.bars, 3600), d1 = cleanCompleted(d1r.bars, 86400), h4 = cleanCompleted(aggregate(h1, 4), 14400);
  if (m15.length < 80 || h1.length < 80 || d1.length < 80) throw new Error("insufficient chart bars");

  const structurePrice = m15.at(-1)!.close;
  let referencePrice = structurePrice, quoteSource = "Yahoo Finance completed M15 reference";
  if (symbol === "EURUSD" && fx?.payload?.rates?.EUR) { referencePrice = 1 / Number(fx.payload.rates.EUR); quoteSource = "exchangerate.dev reference"; }
  if (symbol === "GBPUSD" && fx?.payload?.rates?.GBP) { referencePrice = 1 / Number(fx.payload.rates.GBP); quoteSource = "exchangerate.dev reference"; }

  const trends: Record<string, TrendResult> = { d1: trend(d1), h4: trend(h4), h1: trend(h1), m15: trend(m15) };
  const form = formation(m15, structurePrice), reg = regime(h4, m15, trends.h4, trends.m15), diag = contextDiagnostics(trends, m15, form), sess = session();
  const atr15 = rollingMean(tr(m15), 14).at(-1) ?? null, recent = m15.slice(-20), hi = Math.max(...recent.map(x => x.high)), lo = Math.min(...recent.map(x => x.low)), pos = (structurePrice - lo) / Math.max(hi - lo, 1e-9), prev = d1.at(-1)!, sw = swings(m15.slice(-80)), quality = barQuality(m15, 15);
  const health = {
    structureStatus: quality.freshness,
    structureLagBars: quality.lagBars,
    gapCount96: quality.gaps,
    duplicateCount96: quality.duplicates,
    expectedLastCompletedM15: quality.expectedLastCompletedStart,
    lastM15Bar: quality.lastBarStart,
    structureSource: `${m15r.source} · ${cfg.chart}`,
    referenceSource: quoteSource,
    referenceFetchedAt: fx?.fetchedAt ?? null,
    referenceStatus: fx?.status ?? null,
    generatedAt: new Date().toISOString(),
    executionTruth: "Unavailable: no broker bid/ask feed is connected.",
  };
  const liveResearch = await prospectiveAnalytics(symbol);
  const state: any = {
    symbol, as_of: new Date().toISOString(), reference_price: referencePrice, bid: null, ask: null, spread: null, quote_source: quoteSource, chart_source: m15r.source, market_session: sess,
    d1_trend: trends.d1.label, h4_trend: trends.h4.label, h1_trend: trends.h1.label, m15_trend: trends.m15.label,
    d1_strength: trends.d1.strength, h4_strength: trends.h4.strength, h1_strength: trends.h1.strength, m15_strength: trends.m15.strength,
    regime: reg, formation_stage: form.stage, formation_code: form.code, formation_label: form.label, formation_direction: form.direction, formation_confidence: form.maturity,
    atr15, range_position: clamp(pos, 0, 1), prev_day_high: prev.high, prev_day_low: prev.low, swing_high: sw.lastHigh?.price ?? null, swing_low: sw.lastLow?.price ?? null,
    poi_high: form.poiHigh, poi_low: form.poiLow, distance_to_poi_atr: form.distancePoiAtr,
    research_summary: summaryText(symbol, trends, reg, form, diag), data_health: health,
    details: { trends, formation: form.details, structure_reference_price: structurePrice, diagnostics: diag, liveResearch, researchVersion: "v0.7" }, updated_at: new Date().toISOString(),
  };
  const w = await db.from("market_states").upsert(state, { onConflict: "symbol" }); if (w.error) throw new Error(`state write: ${w.error.message}`);
  await Promise.all([persistBars(symbol, "15m", m15, m15r.source), persistBars(symbol, "1h", h1, h1r.source), persistBars(symbol, "4h", h4, h1r.source), persistBars(symbol, "1d", d1, d1r.source)]);
  const last = await db.from("market_state_history").select("as_of").eq("symbol", symbol).order("as_of", { ascending: false }).limit(1).maybeSingle();
  if (!last.data || Date.now() - new Date(last.data.as_of).getTime() >= 14 * 60_000) {
    const h = await db.from("market_state_history").insert({
      symbol, as_of: state.as_of, reference_price: referencePrice, formation_stage: form.stage, formation_code: form.code, formation_direction: form.direction, regime: reg,
      state: { trends, formation: form, session: sess, quoteSource, structurePrice, rangePosition: state.range_position, diagnostics: diag, dataHealth: health },
    });
    if (h.error) throw new Error(`history write: ${h.error.message}`);
  }
  return state;
}

async function getState(symbol: string, force = false) {
  const q = await db.from("market_states").select("*").eq("symbol", symbol).maybeSingle();
  if (!force && q.data && Date.now() - new Date(q.data.updated_at).getTime() < 240_000) {
    const liveResearch = await prospectiveAnalytics(symbol);
    return { ...q.data, cached: true, details: { ...(q.data.details ?? {}), liveResearch } };
  }
  try { return { ...await refresh(symbol), cached: false }; }
  catch (e) { if (q.data) return { ...q.data, cached: true, refresh_error: String(e), details: { ...(q.data.details ?? {}), liveResearch: await prospectiveAnalytics(symbol) } }; throw e; }
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  try {
    const u = new URL(req.url); let symbols: string[] = [], force = false;
    if (req.method === "POST") { const b = await req.json().catch(() => ({})), raw = b.symbols ?? b.symbol ?? "all"; symbols = raw === "all" ? Object.keys(INSTRUMENTS) : (Array.isArray(raw) ? raw : [raw]); force = Boolean(b.force); }
    else { const raw = u.searchParams.get("symbol") ?? "all"; symbols = raw === "all" ? Object.keys(INSTRUMENTS) : raw.split(","); force = u.searchParams.get("force") === "1"; }
    symbols = symbols.map(x => String(x).toUpperCase()).filter(x => INSTRUMENTS[x]); if (!symbols.length) return response({ error: "No valid instruments" }, 400);
    if (force && !(await cronOk(req))) return response({ error: "unauthorized" }, 401);
    const settled = await Promise.allSettled(symbols.map(s => getState(s, force))), states: any[] = [], errors: any[] = [];
    settled.forEach((r, i) => r.status === "fulfilled" ? states.push(r.value) : errors.push({ symbol: symbols[i], error: String(r.reason) }));
    return response({
      version: "V2 Research Lab v0.7",
      research_only: true,
      live_signals: false,
      generated_at: new Date().toISOString(),
      states,
      errors,
      methodology: {
        purpose: "Prospective FX market-state and V2 formation research; not trade execution.",
        coreMarkets: ["EURUSD", "GBPUSD"],
        executionTruth: "Unavailable without a broker-specific bid/ask feed.",
        eventTimeParity: "Formation geometry uses the last completed M15 close only; display reference prices never change the state machine.",
        trendQuality: "EMA/ATR structure plus Kaufman-style directional efficiency and rolling volatility percentile.",
        regimeDiagnostics: "Volatility percentile, directional efficiency and short-vs-baseline volatility shift diagnostics.",
        prospectivePolicy: "Live history is displayed with sample-size warnings and is not converted into win-rate claims until the sample is materially larger and execution-safe labels exist.",
        validationReference: { barsReplayed: 154665, proxyEntries: 279, stage3Recall: 1.0, stage5Recall: 0.8208, stage6Recall: 0.7133, stage3EightHourConversion: 0.0527 },
      },
    });
  } catch (e) { return response({ error: String(e) }, 500); }
});