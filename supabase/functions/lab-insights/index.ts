import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Cache-Control": "public, max-age=60",
};
const CORE = ["EURUSD", "GBPUSD"];

function response(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" } });
}
function marketClock(now = new Date()) {
  const day = now.getUTCDay(), hour = now.getUTCHours();
  const closed = day === 6 || (day === 0 && hour < 21) || (day === 5 && hour >= 22);
  if (!closed) return { status: "open", label: "FX market open", nextOpen: null };
  const next = new Date(now);
  const add = day === 6 ? 1 : day === 5 ? 2 : 0;
  next.setUTCDate(next.getUTCDate() + add);
  next.setUTCHours(21, 0, 0, 0);
  return { status: "closed", label: "FX market closed", nextOpen: next.toISOString() };
}
function attention(stage: number) {
  if (stage <= 2) return { key: "background", label: "Background", rank: 0 };
  if (stage <= 4) return { key: "watch", label: "Watchlist", rank: 1 };
  if (stage <= 6) return { key: "review", label: "Review now", rank: 2 };
  return { key: "location", label: "At location", rank: 3 };
}
function describeTransition(a: any, b: any) {
  if (!a) return `${b.formation_code?.replaceAll("_", " ") ?? "Initial state"}`;
  const dir = b.formation_direction ? `${b.formation_direction} ` : "";
  if (a.formation_direction !== b.formation_direction && b.formation_direction) return `Direction changed to ${b.formation_direction}; ${b.formation_code.replaceAll("_", " ").toLowerCase()}`;
  if (a.formation_stage !== b.formation_stage) return `${dir}Stage ${a.formation_stage} → Stage ${b.formation_stage}: ${b.formation_code.replaceAll("_", " ").toLowerCase()}`;
  return `${dir}${b.formation_code.replaceAll("_", " ").toLowerCase()}`;
}
function isMeaningfulChange(a: any, b: any) {
  if (!a) return true;
  if (a.formation_direction !== b.formation_direction && (a.formation_stage >= 3 || b.formation_stage >= 3)) return true;
  if (a.formation_stage !== b.formation_stage && Math.max(a.formation_stage, b.formation_stage) >= 3) return true;
  return false;
}
function analytics(rows: any[]) {
  let changes = 0, flicker = 0, stage5Arrivals = 0, stage6Arrivals = 0, stage8Arrivals = 0;
  const meaningful: any[] = [];
  for (let i = 1; i < rows.length; i++) {
    const a = rows[i - 1], b = rows[i];
    const changed = a.formation_stage !== b.formation_stage || a.formation_direction !== b.formation_direction;
    if (changed) changes++;
    if ([0, 1].includes(a.formation_stage) && [0, 1].includes(b.formation_stage) && a.formation_stage !== b.formation_stage) flicker++;
    if (a.formation_stage < 5 && b.formation_stage >= 5) stage5Arrivals++;
    if (a.formation_stage < 6 && b.formation_stage >= 6) stage6Arrivals++;
    if (a.formation_stage < 8 && b.formation_stage >= 8) stage8Arrivals++;
    if (isMeaningfulChange(a, b)) meaningful.push({ at: b.as_of, fromStage: a.formation_stage, toStage: b.formation_stage, direction: b.formation_direction, code: b.formation_code, text: describeTransition(a, b) });
  }
  const obs = rows.length;
  return {
    observations: obs,
    firstSeen: rows[0]?.as_of ?? null,
    lastSeen: rows.at(-1)?.as_of ?? null,
    totalStateChanges: changes,
    lowSignalFlicker: flicker,
    meaningfulChanges: meaningful.length,
    stage5Arrivals,
    stage6Arrivals,
    stage8Arrivals,
    watchObservations: rows.filter(r => r.formation_stage >= 3).length,
    matureObservations: rows.filter(r => r.formation_stage >= 5).length,
    latestMeaningful: meaningful.at(-1) ?? null,
    recentMeaningful: meaningful.slice(-6),
    sampleStatus: obs < 100 ? "early" : obs < 1000 ? "building" : "research-ready",
  };
}
function brief(symbol: string, state: any, stats: any, clock: any) {
  const stage = Number(state?.formation_stage ?? 0), att = attention(stage);
  const d = state?.details?.diagnostics ?? {}, health = state?.data_health ?? {};
  const context = d.structureContext ?? "neutral";
  const direction = state?.formation_direction;
  const marketClosed = clock.status === "closed";
  let headline = "No mature structure needs attention";
  if (stage >= 7) headline = `${direction ? direction[0].toUpperCase() + direction.slice(1) + " " : ""}V2 structure is at the research location`;
  else if (stage >= 5) headline = `${direction ? direction[0].toUpperCase() + direction.slice(1) + " " : ""}structure is mature enough to review`;
  else if (stage >= 3) headline = `${direction ? direction[0].toUpperCase() + direction.slice(1) + " " : ""}sequence is developing`;
  if (marketClosed) headline = `Market closed · ${headline.toLowerCase()}`;

  const reasons: string[] = [];
  reasons.push(`Stage ${stage}/8 · ${state?.formation_label ?? state?.formation_code ?? "unknown"}`);
  if (direction) reasons.push(`Higher-timeframe context is ${context}`);
  reasons.push(`Regime: ${state?.regime ?? "unknown"}`);
  if (d.shiftRisk && d.shiftRisk !== "stable") reasons.push(`Market-change pressure is ${d.shiftRisk}`);
  if (health.structureStatus === "current completed candle") reasons.push("Structure data was current at the last open-market refresh");

  let next = "No action required. Recheck when a clean liquidity event develops.";
  if (stage === 3 || stage === 4) next = "Inspect the chart only if useful; the structural question is whether BOS confirms. Do not anticipate it.";
  if (stage === 5) next = "Review the BOS and look for a clean fresh POI before treating the sequence as mature.";
  if (stage === 6) next = "Review the fresh POI, higher-timeframe context and invalidation. Observe whether price returns without structure failing.";
  if (stage >= 7) next = "Inspect the POI interaction and record what happens next. This remains research, not an execution instruction.";
  if (marketClosed) next = `No live decision is needed while FX is closed. Use the preserved state for review; next expected weekly open is around ${new Date(clock.nextOpen).toUTCString()}.`;

  return {
    attention: att,
    headline,
    reasons,
    next,
    context,
    dominantDirection: d.dominantDirection ?? "mixed",
    alignmentPct: d.alignmentPct ?? 0,
    shiftRisk: d.shiftRisk ?? "stable",
    latestMeaningful: stats.latestMeaningful,
  };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "GET") return response({ error: "GET only" }, 405);
  try {
    const u = new URL(req.url), requested = (u.searchParams.get("symbol") ?? CORE.join(",")).split(",").map(s => s.toUpperCase()).filter(s => CORE.includes(s));
    const symbols = requested.length ? [...new Set(requested)] : CORE;
    const clock = marketClock();
    const output: any[] = [];
    for (const symbol of symbols) {
      const [stateQ, historyQ] = await Promise.all([
        db.from("market_states").select("*").eq("symbol", symbol).maybeSingle(),
        db.from("market_state_history").select("as_of,formation_stage,formation_code,formation_direction,regime,state").eq("symbol", symbol).order("as_of", { ascending: true }).limit(1000),
      ]);
      if (stateQ.error) throw new Error(`${symbol} state: ${stateQ.error.message}`);
      if (historyQ.error) throw new Error(`${symbol} history: ${historyQ.error.message}`);
      const rows = historyQ.data ?? [], stats = analytics(rows), state = stateQ.data;
      output.push({ symbol, stats, brief: brief(symbol, state, stats, clock), stateAsOf: state?.as_of ?? null, structureLastBar: state?.data_health?.lastM15Bar ?? null });
    }
    const totalObs = output.reduce((s, x) => s + x.stats.observations, 0), totalFlicker = output.reduce((s, x) => s + x.stats.lowSignalFlicker, 0), totalChanges = output.reduce((s, x) => s + x.stats.totalStateChanges, 0), mature = output.reduce((s, x) => s + x.stats.stage6Arrivals, 0);
    return response({
      version: "V2 Research Lab insights v0.8",
      generatedAt: new Date().toISOString(),
      market: clock,
      portfolioBrief: {
        headline: clock.status === "closed" ? "FX is closed. Review the last recorded research state; do not interpret missing weekend candles as stale data." : "Use the pair with the highest attention state first; ignore background noise.",
        totalProspectiveObservations: totalObs,
        totalStateChanges: totalChanges,
        lowSignalFlicker: totalFlicker,
        stage6Arrivals: mature,
        finding: totalChanges ? `${totalFlicker} of ${totalChanges} recorded state changes were only Stage 0↔1 flicker. v0.8 therefore suppresses low-signal churn in the primary experience.` : "The live stream is still initializing.",
        inferenceGate: totalObs < 200 ? "Too early for live outcome-rate inference." : "Descriptive transition analysis is becoming more useful; execution-safe profitability inference is still blocked.",
      },
      pairs: output,
      productPolicy: {
        primaryQuestion: "What deserves attention now, what changed, why, and what should I inspect next?",
        detailsPolicy: "Quant metrics remain available for investigation but are secondary to the research brief.",
        signalPolicy: "No buy/sell instruction and no win probability until execution-safe labels exist.",
      },
    });
  } catch (e) { return response({ error: String(e) }, 500); }
});