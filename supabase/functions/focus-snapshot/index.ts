import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SB = Deno.env.get("SUPABASE_URL")!;
const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = createClient(SB, KEY, { auth: { persistSession: false } });
const H = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "public, max-age=5, s-maxage=10, stale-while-revalidate=50",
  "Access-Control-Allow-Origin": "*",
};
const SYMS = ["EURUSD", "GBPUSD", "XAUUSD"];

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: H });
  if (req.method !== "GET") return new Response(JSON.stringify({ error: "GET only" }), { status: 405, headers: H });
  const started = performance.now();
  try {
    const [sq, tq] = await Promise.all([
      db.from("market_states").select("*").in("symbol", SYMS),
      db.from("paper_trades")
        .select("trade_key,symbol,direction,status,armed_at,entry_at,exit_at,entry_price,stop_price,target_price,risk_distance,gross_r,mfe_r,mae_r,lifecycle_phase,setup_condition,pending_age_bars,focus_active,updated_at")
        .in("symbol", ["EURUSD", "GBPUSD"])
        .order("armed_at", { ascending: false })
        .limit(30),
    ]);
    if (sq.error || tq.error) throw new Error(sq.error?.message || tq.error?.message || "snapshot query failed");
    return new Response(JSON.stringify({
      ok: true,
      generatedAt: new Date().toISOString(),
      serverMs: Math.round(performance.now() - started),
      states: sq.data ?? [],
      trades: tq.data ?? [],
    }), { headers: H });
  } catch (e) {
    console.error(e);
    return new Response(JSON.stringify({ error: e instanceof Error ? e.message : String(e) }), { status: 500, headers: H });
  }
});
