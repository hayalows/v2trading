import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SB = Deno.env.get("SUPABASE_URL")!;
const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const WH = (Deno.env.get("DISCORD_WEBHOOK_URL") ?? "").trim();
const db = createClient(SB, KEY, { auth: { persistSession: false } });
const H = { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" };
const R = (x: unknown, s = 200) => new Response(JSON.stringify(x), { status: s, headers: H });

async function post(embed: unknown) {
  if (!WH) throw new Error("DISCORD_WEBHOOK_URL missing");
  const u = new URL(WH);
  u.searchParams.set("wait", "true");
  const r = await fetch(u, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "V2 Trading", allowed_mentions: { parse: [] }, embeds: [embed] }),
  });
  const t = await r.text();
  if (!r.ok) throw new Error(`Discord ${r.status}: ${t.slice(0, 240)}`);
  return JSON.parse(t);
}

Deno.serve(async (req) => {
  if (req.method !== "GET") return R({ error: "GET only" }, 405);
  try {
    const stateKey = "project_update_20260818_ui_health_realtime_v1";
    const old = await db.from("discord_alert_state").select("snapshot").eq("state_key", stateKey).maybeSingle();
    if (old.data) return R({ ok: true, alreadySent: true, messageId: old.data.snapshot?.messageId ?? null });

    const embed = {
      title: "V2 System Update · UI, reliability & near-live monitoring",
      description: "V2 has gone through a substantial reliability and UX pass. The goal was simple: keep the trading engine dependable, make the app easier to understand at a glance, and make every important stage visible without clutter.",
      color: 9296639,
      fields: [
        { name: "Interface rebuilt on a safer foundation", value: "The app navigation is now independent from charts, fonts and slow data calls. Home, Trades, Research and System remain usable even if an external service is delayed. A stable recovery page is also preserved as a fallback.", inline: false },
        { name: "Mobile UX is clearer", value: "The Home screen now uses stronger information hierarchy: readable typography, a compact paper-account summary, clearer EURUSD / GBPUSD instrument cards, consistent SVG icons and fewer competing boxes. Important information is shown first; secondary detail lives in the deeper views.", inline: false },
        { name: "Trades are easier to audit", value: "Each paper trade now surfaces result, R, P&L, entry / exit timing, plan lead time, hold time, setup quality and POI → Entry → SL / TP geometry. Clean, weakened, extended and long-tail contexts are descriptive research labels only and do not rewrite V2 results.", inline: false },
        { name: "Health & diagnostics are now built in", value: "System monitors frontend errors, EURUSD / GBPUSD completed-candle freshness, gaps, duplicates, lag, paper-engine heartbeat, portfolio status, Discord heartbeat, research schedulers and execution-audit freshness. A frontend problem should no longer look like the whole trading system is dead.", inline: false },
        { name: "Near-live operation", value: "The paper engine and core Discord monitoring run every minute. Primary market refreshes are aligned just after candle boundaries so completed data is more likely to be finalized before V2 evaluates it. The UI refreshes automatically while visible, without changing the completed-M15 decision model.", inline: false },
        { name: "Discord alerts improved", value: "Milestone messages now separate the level crossed from the current R after a retracement — e.g. ‘Crossed +2.0R · peak +2.03R · current +1.67R’ — so alerts describe what actually happened instead of implying price is still at the milestone.", inline: false },
        { name: "What happens going forward", value: "V2 will keep scanning EURUSD and GBPUSD, progressing setups through the defined stages, freezing valid paper plans, monitoring entries / exits, updating the paper account and sending Discord alerts. Health checks continue in parallel. V3.4 / V3.5 remain research-only unless prospective evidence justifies promotion.", inline: false },
        { name: "Trading boundary remains unchanged", value: "This work improved reliability, observability and UX — not the strategy rules. V2 still uses the frozen baseline logic and 1% paper risk. Research evidence remains separate from the canonical account.", inline: false },
      ],
      footer: { text: "V2 Trading · research / paper trading system update" },
      timestamp: new Date().toISOString(),
    };

    const msg = await post(embed);
    const sentAt = new Date().toISOString();
    await db.from("discord_alert_log").insert({ symbol: null, event_type: "project_update", discord_message_id: msg.id ?? null, payload: embed, sent_at: sentAt });
    await db.from("discord_alert_state").upsert({ state_key: stateKey, snapshot: { messageId: msg.id ?? null, title: embed.title }, last_sent_at: sentAt, updated_at: sentAt }, { onConflict: "state_key" });
    return R({ ok: true, alreadySent: false, messageId: msg.id ?? null, title: embed.title });
  } catch (e) {
    console.error(e);
    return R({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
