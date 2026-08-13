import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SB_URL = Deno.env.get("SUPABASE_URL");
const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
const db = createClient(SB_URL, KEY, { auth: { persistSession: false } });
const SYMBOLS = ["EURUSD", "GBPUSD"];
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization,x-client-info,apikey,content-type",
  "Access-Control-Allow-Methods": "GET,OPTIONS",
  "Cache-Control": "no-store",
};
const reply = (x: unknown, status = 200) => new Response(JSON.stringify(x), { status, headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" } });
const n = (v: unknown) => Number.isFinite(Number(v)) ? Number(v) : null;
const ageMinutes = (ts?: string | null) => ts ? Math.max(0, (Date.now() - new Date(ts).getTime()) / 60000) : null;

function quality(t: any) {
  if (!t) return { code: "NO_SETUP", label: "No setup to grade", tone: "neutral", reason: "V2 is waiting for a mature paper setup before showing a quality read.", next: "Wait for the normal sweep → structure break → entry-zone sequence." };
  if (t.status === "invalid" || t.poi_lifecycle_state === "invalidated_close_through") {
    return { code: "BROKEN", label: "Broken setup", tone: "bad", reason: "The setup is no longer structurally valid.", next: "Do not treat this plan as an active opportunity." };
  }
  if (t.entry_at) {
    if (["partially_mitigated", "partially_mitigated_after_target"].includes(t.setup_condition)) {
      return { code: "WEAKENED", label: "Weakened setup", tone: "warn", reason: "Price touched the entry zone earlier before it finally reached the midpoint.", next: "Keep the paper trade under the normal rules, but treat the setup as lower quality rather than a fresh first interaction." };
    }
    if (t.setup_condition === "target_delivered_before_entry") {
      return { code: "LATE_RETURN", label: "Late return", tone: "warn", reason: "The move had already travelled about 2.5R before returning to the entry.", next: "Treat this as a recycled move, not the cleanest version of the setup." };
    }
    if (t.first_zone_touch_at && new Date(t.first_zone_touch_at).getTime() === new Date(t.entry_at).getTime()) {
      return { code: "STRONG_INTERACTION", label: "Strong interaction", tone: "good", reason: "Price reached the midpoint on its first recorded visit to the zone.", next: "The entry still follows the same stop and target rules; this is a quality read, not a guarantee of a win." };
    }
    return { code: "CLEAN_ENTRY", label: "Clean entry", tone: "good", reason: "The midpoint entry was reached without a recorded shallow-touch warning.", next: "Continue tracking the frozen paper stop and target." };
  }
  if (t.first_zone_touch_at) {
    const weakened = ["partially_mitigated", "partially_mitigated_after_target"].includes(t.setup_condition);
    if (weakened) return { code: "EARLY_WEAKENING", label: "Early touch — weaker", tone: "warn", reason: "Price has touched the zone but has not reached the midpoint. Historically, a shallow first touch weakened later entries.", next: "Wait for the normal midpoint rule; do not count the edge touch as an entry." };
    return { code: "WATCH_TOUCH", label: "Zone interaction", tone: "neutral", reason: "Price has started interacting with the zone, but the midpoint has not been reached yet.", next: "The next useful information is whether the first interaction reaches the midpoint cleanly." };
  }
  return { code: "WATCHING", label: "Waiting for first interaction", tone: "neutral", reason: "The setup exists, but price has not touched the entry zone yet.", next: "No winner/loser grade is justified yet. Wait for the first interaction with the zone." };
}

async function micro(symbol: string) {
  const q = await db.from("fx_microstructure_1m")
    .select("ts,spread_mean_pips,tick_count,source")
    .eq("symbol", symbol).order("ts", { ascending: false }).limit(1).maybeSingle();
  if (q.error || !q.data) return null;
  return { ...q.data, ageMinutes: ageMinutes(q.data.ts) };
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "GET") return reply({ error: "GET only" }, 405);
  try {
    const u = new URL(req.url);
    const requested = (u.searchParams.get("symbol") || SYMBOLS.join(",")).split(",").map(x => x.trim().toUpperCase()).filter(x => SYMBOLS.includes(x));
    const symbols = requested.length ? requested : SYMBOLS;
    const q = await db.from("paper_trades").select("*").in("symbol", symbols).order("armed_at", { ascending: false }).limit(100);
    if (q.error) throw new Error(q.error.message);
    const trades = q.data || [];
    const entered = trades.filter((t: any) => t.entry_at);
    const wins = entered.filter((t: any) => t.status === "win").length;
    const losses = entered.filter((t: any) => t.status === "loss").length;
    const timeouts = entered.filter((t: any) => t.status === "timeout" && t.gross_r != null).length;
    const ambiguous = entered.filter((t: any) => t.status === "ambiguous").length;
    const decisive = wins + losses;
    const scored = decisive + timeouts;
    const keys = trades.map((t: any) => t.trade_key);
    let auditMap = new Map<string, any>();
    if (keys.length) {
      const a = await db.from("paper_trade_execution_audit").select("trade_key,audit_status,entry_confirmed,entry_at_tick,entry_spread_pips,updated_at").in("trade_key", keys);
      if (!a.error) auditMap = new Map((a.data || []).map((x: any) => [x.trade_key, x]));
    }
    const microRows = await Promise.all(symbols.map(async s => [s, await micro(s)] as const));
    const microMap = new Map(microRows);
    const current: Record<string, any> = {};
    for (const symbol of symbols) {
      const xs = trades.filter((t: any) => t.symbol === symbol);
      const t = xs.find((x: any) => x.status === "open") || xs.find((x: any) => x.status === "armed" && x.focus_active !== false) || xs.find((x: any) => x.status === "armed") || null;
      const ql = quality(t);
      const riskPips = t ? n(Number(t.risk_distance) / 0.0001) : null;
      const m: any = microMap.get(symbol);
      const spread = n(m?.spread_mean_pips);
      const spreadRiskPct = riskPips && spread != null ? 100 * spread / riskPips : null;
      const friction = !m || m.ageMinutes == null || m.ageMinutes > 30 ? "UNKNOWN" : spreadRiskPct != null && spreadRiskPct >= 25 ? "HIGH" : spreadRiskPct != null && spreadRiskPct >= 15 ? "ELEVATED" : "NORMAL";
      current[symbol] = {
        symbol,
        tradeKey: t?.trade_key || null,
        direction: t?.direction || null,
        status: t?.status || null,
        quality: ql,
        risk: t ? {
          pips: riskPips,
          stopPolicyVersion: t.context?.stop_policy_version || "legacy_structural",
          floorPips: n(t.context?.stop_floor_pips),
          floorApplied: t.context?.stop_floor_applied === true,
          dollarRiskRule: "1% of realized paper balance at entry; wider stop means smaller position size",
        } : null,
        friction: { status: friction, indicativeSpreadPips: spread, spreadAsPctOfRisk: spreadRiskPct, sourceAgeMinutes: m?.ageMinutes ?? null },
        executionCheck: t ? auditMap.get(t.trade_key) || null : null,
      };
    }
    return reply({
      version: "V3.1 setup quality",
      generatedAt: new Date().toISOString(),
      researchOnly: true,
      winRate: {
        entered: entered.length,
        wins, losses, timeouts, ambiguous,
        decisiveWinRatePct: decisive ? 100 * wins / decisive : null,
        scoredClosureWinSharePct: scored ? 100 * wins / scored : null,
        note: "Decisive win rate uses wins/(wins+losses). Scored-closure win share also includes numeric timeouts. Ambiguous outcomes are excluded.",
      },
      current,
      historicalInteractionEvidence: {
        completedYears: "2022-2025",
        directFirstInteraction: { n: 316, winRatePct: 42.405, meanR: 0.5004 },
        priorShallowTouch: { n: 805, winRatePct: 27.329, meanR: -0.00067 },
        closeThroughDistal: { n: 48, winRatePct: 8.33, meanR: -0.7083 },
        directMinusShallow: { winRateDeltaPctPoints: 15.08, bootstrap95PctPoints: [6.42, 23.92], meanRDelta: 0.501, bootstrap95R: [0.199, 0.807] },
        boundary: "These are historical public-price research rates, not a probability for the current trade.",
      },
      methodology: {
        preEntryGeometry: "Rejected as a winner detector: walk-forward AUC stayed close to random and Brier score did not improve reliably.",
        earliestUsefulSignal: "The first interaction with the POI. Direct midpoint interaction was materially stronger than a prior shallow touch.",
        microstructure: "Spread/execution evidence is a friction and data-quality modifier only; it is not promoted to a win predictor.",
        automaticTradeChange: false,
      },
    });
  } catch (e) {
    return reply({ error: String(e) }, 500);
  }
});
