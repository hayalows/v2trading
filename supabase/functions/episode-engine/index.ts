import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const db = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { auth: { persistSession: false } },
);

const CORE = ["EURUSD", "GBPUSD"];
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Cache-Control": "no-store",
};
const M15_MS = 15 * 60_000;
const HORIZONS = [15, 30, 60, 120, 240] as const;

type Row = {
  symbol: string;
  as_of: string;
  formation_stage: number;
  formation_code: string | null;
  formation_direction: "long" | "short" | null;
  regime: string | null;
  m15_trend: string | null;
  h1_trend: string | null;
  h4_trend: string | null;
  d1_trend: string | null;
  state: any;
};
type Bar = { ts: string; open: number; high: number; low: number; close: number };
type Episode = {
  episode_key: string;
  symbol: string;
  direction: "long" | "short";
  status: "active" | "ended";
  started_at: string;
  ended_at: string | null;
  end_reason: string | null;
  last_seen_at: string;
  max_stage: number;
  stage3_at: string | null;
  stage4_at: string | null;
  stage5_at: string | null;
  stage6_at: string | null;
  stage7_at: string | null;
  stage8_at: string | null;
  stage3_price: number | null;
  stage5_price: number | null;
  stage6_price: number | null;
  stage3_atr: number | null;
  stage5_atr: number | null;
  stage6_atr: number | null;
  anchor_context: Record<string, unknown>;
  source_meta: Record<string, unknown>;
};

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" },
  });
}
function n(v: unknown): number | null {
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}
function iso(v: string | Date) { return new Date(v).toISOString(); }
function addMinutes(v: string, minutes: number) { return new Date(new Date(v).getTime() + minutes * 60_000).toISOString(); }
function round(v: number | null, digits = 6) {
  if (v == null || !Number.isFinite(v)) return null;
  const p = 10 ** digits;
  return Math.round(v * p) / p;
}
function eventInfo(row: Row) {
  const state = row.state ?? {};
  const health = state.dataHealth ?? state.data_health ?? {};
  const barStart = health.last_m15_bar ?? health.lastM15Bar ?? null;
  const price = n(state.structurePrice ?? health.structure_reference_price ?? health.structureReferencePrice);
  return {
    observedAt: iso(row.as_of),
    eventAt: barStart ? addMinutes(barStart, 15) : iso(row.as_of),
    barStart: barStart ? iso(barStart) : null,
    price,
    source: health.structure_source ?? health.structureSource ?? null,
  };
}
function context(row: Row) {
  const s = row.state ?? {}, d = s.diagnostics ?? s.details?.diagnostics ?? {};
  return {
    observedAt: iso(row.as_of),
    stage: row.formation_stage,
    code: row.formation_code,
    direction: row.formation_direction,
    regime: row.regime,
    trends: {
      d1: row.d1_trend,
      h4: row.h4_trend,
      h1: row.h1_trend,
      m15: row.m15_trend,
    },
    session: s.session ?? null,
    rangePosition: s.rangePosition ?? null,
    diagnostics: d,
    formation: s.formation ?? null,
  };
}
function episodeKey(symbol: string, direction: string, startedAt: string) {
  return `${symbol}:${direction}:${new Date(startedAt).toISOString()}`;
}
function newEpisode(row: Row): Episode {
  const e = eventInfo(row), dir = row.formation_direction!;
  return {
    episode_key: episodeKey(row.symbol, dir, row.as_of),
    symbol: row.symbol,
    direction: dir,
    status: "active",
    started_at: iso(row.as_of),
    ended_at: null,
    end_reason: null,
    last_seen_at: iso(row.as_of),
    max_stage: Math.max(3, row.formation_stage),
    stage3_at: null,
    stage4_at: null,
    stage5_at: null,
    stage6_at: null,
    stage7_at: null,
    stage8_at: null,
    stage3_price: null,
    stage5_price: null,
    stage6_price: null,
    stage3_atr: null,
    stage5_atr: null,
    stage6_atr: null,
    anchor_context: {},
    source_meta: { firstStructureEventAt: e.eventAt, firstBarStart: e.barStart, structureSource: e.source },
  };
}
function markStages(ep: Episode, row: Row) {
  const stage = Number(row.formation_stage), e = eventInfo(row);
  ep.last_seen_at = iso(row.as_of);
  ep.max_stage = Math.max(ep.max_stage, stage);
  const anchors = [3, 4, 5, 6, 7, 8];
  for (const a of anchors) {
    if (stage < a) continue;
    const key = `stage${a}_at` as keyof Episode;
    if (ep[key] == null) (ep as any)[key] = iso(row.as_of);
  }
  for (const a of [3, 5, 6]) {
    if (stage < a) continue;
    const priceKey = `stage${a}_price`;
    if ((ep as any)[priceKey] == null && e.price != null) (ep as any)[priceKey] = e.price;
    const ctxKey = `stage${a}`;
    if (!(ctxKey in ep.anchor_context)) {
      ep.anchor_context[ctxKey] = { ...context(row), eventAt: e.eventAt, structurePrice: e.price, barStart: e.barStart };
    }
  }
  ep.source_meta = { ...ep.source_meta, lastStructureEventAt: e.eventAt, lastBarStart: e.barStart, structureSource: e.source };
}
function closeEpisode(ep: Episode, at: string, reason: string) {
  ep.status = "ended";
  ep.ended_at = iso(at);
  ep.end_reason = reason;
}
function buildEpisodes(rows: Row[]) {
  const out: Episode[] = [];
  let current: Episode | null = null;
  for (const row of rows) {
    const stage = Number(row.formation_stage ?? 0), dir = row.formation_direction;
    if (stage >= 3 && dir) {
      if (!current) current = newEpisode(row);
      else if (current.direction !== dir) {
        closeEpisode(current, row.as_of, "direction_flip");
        out.push(current);
        current = newEpisode(row);
      }
      markStages(current, row);
    } else if (current) {
      closeEpisode(current, row.as_of, "formation_reset");
      out.push(current);
      current = null;
    }
  }
  if (current) out.push(current);
  return out;
}
function barMs(b: Bar) { return new Date(b.ts).getTime(); }
function trueRanges(bars: Bar[]) {
  return bars.map((b, i) => i === 0
    ? b.high - b.low
    : Math.max(b.high - b.low, Math.abs(b.high - bars[i - 1].close), Math.abs(b.low - bars[i - 1].close)));
}
function atrAt(bars: Bar[], eventAt: string) {
  const t = new Date(eventAt).getTime();
  const eligible = bars.filter(b => barMs(b) + M15_MS <= t);
  if (eligible.length < 14) return null;
  const tr = trueRanges(eligible);
  const xs = tr.slice(-14);
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}
function closeAtHorizon(bars: Bar[], anchorAt: string, minutes: number) {
  const a = new Date(anchorAt).getTime(), target = a + minutes * 60_000;
  const candidates = bars.filter(b => barMs(b) >= a && barMs(b) + M15_MS <= target);
  return candidates.at(-1)?.close ?? null;
}
function excursion(bars: Bar[], anchorAt: string, minutes: number, anchor: number, direction: "long" | "short", atr: number | null) {
  if (!atr || atr <= 0) return { mfe: null, mae: null };
  const a = new Date(anchorAt).getTime(), end = a + minutes * 60_000;
  const xs = bars.filter(b => barMs(b) >= a && barMs(b) + M15_MS <= end);
  if (!xs.length) return { mfe: null, mae: null };
  const maxH = Math.max(...xs.map(x => x.high)), minL = Math.min(...xs.map(x => x.low));
  if (direction === "long") return { mfe: (maxH - anchor) / atr, mae: (anchor - minL) / atr };
  return { mfe: (anchor - minL) / atr, mae: (maxH - anchor) / atr };
}
function anchorFromEpisode(ep: Episode, stage: 3 | 5 | 6) {
  const ctx = (ep.anchor_context as any)?.[`stage${stage}`];
  const observed = (ep as any)[`stage${stage}_at`] as string | null;
  const price = n((ep as any)[`stage${stage}_price`]);
  if (!ctx || !observed || price == null) return null;
  return { observedAt: observed, eventAt: ctx.eventAt ?? observed, price };
}
function outcome(ep: Episode, stage: 3 | 5 | 6, bars: Bar[]) {
  const a = anchorFromEpisode(ep, stage);
  if (!a) return null;
  const latestEnd = bars.length ? barMs(bars.at(-1)!) + M15_MS : 0;
  const anchorMs = new Date(a.eventAt).getTime();
  const atr = atrAt(bars, a.eventAt);
  const factor = ep.direction === "long" ? 1 : -1;
  const ret: Record<number, number | null> = {};
  let complete = 0;
  for (const h of HORIZONS) {
    if (latestEnd < anchorMs + h * 60_000) { ret[h] = null; continue; }
    const c = closeAtHorizon(bars, a.eventAt, h);
    ret[h] = c == null ? null : ((c / a.price) - 1) * 10_000;
    if (ret[h] != null) complete = h;
  }
  const x1 = complete >= 60 ? excursion(bars, a.eventAt, 60, a.price, ep.direction, atr) : { mfe: null, mae: null };
  const x4 = complete >= 240 ? excursion(bars, a.eventAt, 240, a.price, ep.direction, atr) : { mfe: null, mae: null };
  return {
    episode_key: ep.episode_key,
    anchor_stage: stage,
    anchor_at: a.eventAt,
    direction: ep.direction,
    anchor_price: a.price,
    atr_at_anchor: round(atr, 8),
    ret_15m_bps: round(ret[15]), ret_30m_bps: round(ret[30]), ret_1h_bps: round(ret[60]), ret_2h_bps: round(ret[120]), ret_4h_bps: round(ret[240]),
    signed_ret_15m_bps: round(ret[15] == null ? null : ret[15]! * factor),
    signed_ret_30m_bps: round(ret[30] == null ? null : ret[30]! * factor),
    signed_ret_1h_bps: round(ret[60] == null ? null : ret[60]! * factor),
    signed_ret_2h_bps: round(ret[120] == null ? null : ret[120]! * factor),
    signed_ret_4h_bps: round(ret[240] == null ? null : ret[240]! * factor),
    mfe_1h_atr: round(x1.mfe), mae_1h_atr: round(x1.mae), mfe_4h_atr: round(x4.mfe), mae_4h_atr: round(x4.mae),
    complete_through_minutes: complete,
    updated_at: new Date().toISOString(),
  };
}
function evidenceLabel(n: number) {
  if (n < 10) return "insufficient";
  if (n < 30) return "early";
  if (n < 100) return "building";
  return "research-ready";
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (!["GET", "POST"].includes(req.method)) return response({ error: "GET or POST only" }, 405);
  try {
    const result: any[] = [];
    for (const symbol of CORE) {
      const [historyQ, barsQ] = await Promise.all([
        db.from("market_state_history")
          .select("symbol,as_of,formation_stage,formation_code,formation_direction,regime,m15_trend,h1_trend,h4_trend,d1_trend,state")
          .eq("symbol", symbol).order("as_of", { ascending: true }).limit(5000),
        db.from("market_bars").select("ts,open,high,low,close").eq("symbol", symbol).eq("timeframe", "15m").order("ts", { ascending: true }).limit(10000),
      ]);
      if (historyQ.error) throw new Error(`${symbol} history: ${historyQ.error.message}`);
      if (barsQ.error) throw new Error(`${symbol} bars: ${barsQ.error.message}`);
      const rows = (historyQ.data ?? []) as Row[], bars = (barsQ.data ?? []) as Bar[];
      const episodes = buildEpisodes(rows);
      if (episodes.length) {
        const payload = episodes.map(e => ({ ...e, updated_at: new Date().toISOString() }));
        const q = await db.from("formation_episodes").upsert(payload, { onConflict: "episode_key" });
        if (q.error) throw new Error(`${symbol} episode upsert: ${q.error.message}`);
      }
      const outcomes = episodes.flatMap(ep => ([3, 5, 6] as const).map(s => outcome(ep, s, bars)).filter(Boolean));
      if (outcomes.length) {
        const q = await db.from("episode_outcomes").upsert(outcomes, { onConflict: "episode_key,anchor_stage" });
        if (q.error) throw new Error(`${symbol} outcome upsert: ${q.error.message}`);
      }
      const active = episodes.find(e => e.status === "active") ?? null;
      const complete6 = outcomes.filter((x: any) => x.anchor_stage === 6 && x.complete_through_minutes >= 60).length;
      result.push({ symbol, historyRows: rows.length, episodes: episodes.length, activeEpisode: active?.episode_key ?? null, outcomes: outcomes.length, completedStage6_1h: complete6, evidence: evidenceLabel(complete6) });
    }
    return response({ version: "V2 episode engine v1.1", generatedAt: new Date().toISOString(), result });
  } catch (e) {
    console.error(e);
    return response({ error: String(e) }, 500);
  }
});
