import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const URL = Deno.env.get("SUPABASE_URL")!;
const KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const WEBHOOK = Deno.env.get("DISCORD_WEBHOOK_URL") ?? "";
const db = createClient(URL, KEY, { auth: { persistSession: false } });
const PAIRS = ["EURUSD", "GBPUSD"];
const ALERT_STAGES = new Set([3, 5, 6, 7, 8]);
const CLOSED = new Set(["win", "loss", "timeout", "ambiguous", "expired", "invalid"]);
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization,x-client-info,apikey,content-type",
  "Access-Control-Allow-Methods": "GET,OPTIONS",
  "Cache-Control": "no-store",
};
const json = (x: unknown, status = 200) => new Response(JSON.stringify(x), {
  status,
  headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" },
});
const fmt = (v: unknown, d = 5) => Number.isFinite(Number(v)) ? Number(v).toFixed(d) : "—";
const upper = (v: unknown) => String(v ?? "—").toUpperCase();

function validWebhook(raw: string) {
  try {
    const u = new URL(raw);
    return u.protocol === "https:" && u.hostname === "discord.com" && u.pathname.startsWith("/api/webhooks/");
  } catch { return false; }
}

function snap(pair: any, trade: any) {
  return {
    campaignKey: pair?.campaign?.campaign_key ?? null,
    stage: Number(pair?.formation?.stage ?? 0),
    direction: pair?.formation?.direction ?? null,
    decisionMode: pair?.decision?.mode ?? null,
    dataTrust: pair?.decision?.dataTrust?.level ?? null,
    router: pair?.decision?.router?.route ?? "ABSTAIN",
    tradeKey: trade?.trade_key ?? null,
    tradeStatus: trade?.status ?? null,
  };
}

function embed(pair: any, title: string, description: string) {
  const f = pair?.formation ?? {}, d = pair?.decision ?? {};
  return {
    title: `${pair.symbol} · ${title}`,
    description,
    fields: [
      { name: "Formation", value: `${upper(f.direction)} · Stage ${Number(f.stage ?? 0)}/8`, inline: true },
      { name: "Decision", value: String(d.mode ?? "—"), inline: true },
      { name: "Data", value: String(d.dataTrust?.level ?? "—"), inline: true },
      { name: "Model", value: String(d.router?.route ?? "ABSTAIN"), inline: true },
      { name: "Price", value: fmt(pair?.referencePrice), inline: true },
      { name: "As of", value: pair?.asOf ? new Date(pair.asOf).toISOString().replace("T", " ").replace(".000Z", " UTC") : "—", inline: true },
    ],
    footer: { text: "V2 research-only decision intelligence · not a live trading instruction" },
    timestamp: new Date().toISOString(),
  };
}

type Event = { type: string; title: string; description: string };

function stageEvent(pair: any, old: any): Event | null {
  const stage = Number(pair?.formation?.stage ?? 0);
  const campaign = pair?.campaign?.campaign_key ?? null;
  const changed = old && (old.campaignKey !== campaign || old.stage !== stage || old.direction !== pair?.formation?.direction);
  if (!changed || !ALERT_STAGES.has(stage)) return null;
  const map: Record<number, [string, string]> = {
    3: ["Sweep confirmed", "Liquidity sweep recorded. V2 is waiting for same-direction BOS."],
    5: ["BOS confirmed", "Break of structure is confirmed on completed M15 data. Fresh POI identification is next."],
    6: ["Fresh POI identified", `A fresh POI is frozen. Baseline stays at the 50% midpoint. POI: ${fmt(pair?.formation?.poiLow)}–${fmt(pair?.formation?.poiHigh)}.`],
    7: ["Approaching POI", `Price is approaching the frozen POI. Distance: ${fmt(pair?.formation?.distanceToPoiAtr, 2)} ATR.`],
    8: ["Entry zone reached", "The frozen research entry zone has been reached. This is a paper-research event, not a broker instruction."],
  };
  const [title, description] = map[stage];
  return { type: `stage_${stage}`, title, description };
}

function tradeEvent(trade: any, old: any): Event | null {
  if (!trade || !old) return null;
  const changed = old.tradeKey !== trade.trade_key || old.tradeStatus !== trade.status;
  if (!changed) return null;
  if (trade.status === "armed") return {
    type: "paper_armed", title: "Paper plan armed",
    description: `${upper(trade.direction)} research plan · Entry ${fmt(trade.entry_price)} · Stop ${fmt(trade.stop_price)} · Target ${fmt(trade.target_price)} · Risk ${fmt(trade.risk_atr, 2)} ATR.`,
  };
  if (trade.status === "open") return {
    type: "paper_open", title: "Paper entry recorded",
    description: `${upper(trade.direction)} paper entry ${fmt(trade.entry_price)} · frozen stop ${fmt(trade.stop_price)} · target ${fmt(trade.target_price)}.`,
  };
  if (CLOSED.has(trade.status)) return {
    type: `paper_${trade.status}`, title: `Paper trade ${upper(trade.status)}`,
    description: `${upper(trade.direction)} paper trade resolved ${upper(trade.status)}${Number.isFinite(Number(trade.gross_r)) ? ` · ${Number(trade.gross_r).toFixed(2)}R` : ""}${Number.isFinite(Number(trade.exit_price)) ? ` · exit ${fmt(trade.exit_price)}` : ""}.`,
  };
  return null;
}

function trustEvent(pair: any, old: any): Event | null {
  if (!old) return null;
  const now = pair?.decision?.dataTrust?.level ?? null;
  if (old.dataTrust === now) return null;
  if (now === "BLOCKED") return {
    type: "data_blocked", title: "Data blocked",
    description: `V2 has stopped formation/model influence because a structure-quality gate failed. ${pair?.decision?.dataTrust?.reason ?? ""}`,
  };
  if (old.dataTrust === "BLOCKED") return {
    type: "data_restored", title: "Data restored",
    description: `The structure feed recovered to ${now}. Research-state tracking can resume.`,
  };
  return null;
}

function modeEvent(pair: any, old: any): Event | null {
  if (old && pair?.decision?.mode === "DUAL_ATTENTION" && old.decisionMode !== "DUAL_ATTENTION") return {
    type: "dual_attention", title: "Dual attention",
    description: "An existing paper plan/trade and a new opposite-direction formation coexist. They remain independent; V2 will not auto-reverse the existing paper trade.",
  };
  return null;
}

function routerEvent(pair: any, old: any): Event | null {
  if (!old) return null;
  const now = pair?.decision?.router?.route ?? "ABSTAIN";
  if (!old.router || old.router === now) return null;
  return now === "ABSTAIN"
    ? { type: "router_abstain", title: "Model router abstaining", description: "Prospective model evidence no longer clears the routing gate. Structural engine remains primary." }
    : { type: "router_active", title: `Model router → ${now}`, description: `${now} cleared the prospective routing gate. Raw probabilities remain hidden.` };
}

async function postDiscord(embeds: any[]) {
  const u = new URL(WEBHOOK); u.searchParams.set("wait", "true");
  const r = await fetch(u.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "V2 Decision Intelligence", allowed_mentions: { parse: [] }, embeds }),
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`Discord ${r.status}: ${text.slice(0, 300)}`);
  try { return JSON.parse(text); } catch { return { id: null }; }
}

async function getState(key: string) {
  const q = await db.from("discord_alert_state").select("snapshot,updated_at,last_sent_at").eq("state_key", key).maybeSingle();
  if (q.error) throw new Error(q.error.message);
  return q.data;
}
async function saveState(key: string, snapshot: any, sent = false) {
  const row: any = { state_key: key, snapshot, updated_at: new Date().toISOString() };
  if (sent) row.last_sent_at = new Date().toISOString();
  const q = await db.from("discord_alert_state").upsert(row, { onConflict: "state_key" });
  if (q.error) throw new Error(q.error.message);
}
async function log(symbol: string | null, events: Event[], payloads: any[], messageId: string | null) {
  if (!events.length) return;
  const rows = events.map((e, i) => ({ symbol, event_type: e.type, discord_message_id: messageId, payload: payloads[i], sent_at: new Date().toISOString() }));
  const q = await db.from("discord_alert_log").insert(rows);
  if (q.error) console.error("discord alert log failed", q.error.message);
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "GET") return json({ error: "GET only" }, 405);
  try {
    if (!validWebhook(WEBHOOK)) return json({ configured: false, reason: "Set DISCORD_WEBHOOK_URL to an official Discord incoming webhook URL." }, 503);

    const system = await getState("_system");
    if (system?.updated_at && Date.now() - Date.parse(system.updated_at) < 210_000)
      return json({ ok: true, configured: true, skipped: "throttled" });

    const [intelRes, trades] = await Promise.all([
      fetch(`${URL}/functions/v1/decision-intelligence`, { headers: { "Cache-Control": "no-cache" } }),
      db.from("paper_trades").select("trade_key,symbol,direction,status,entry_price,stop_price,target_price,risk_atr,exit_price,gross_r,armed_at").in("symbol", PAIRS).order("armed_at", { ascending: false }).limit(20),
    ]);
    if (!intelRes.ok) throw new Error(`decision-intelligence ${intelRes.status}`);
    if (trades.error) throw new Error(trades.error.message);
    const intel = await intelRes.json();
    const pairs = Array.isArray(intel?.pairs) ? intel.pairs : [];
    const latest = new Map<string, any>();
    for (const t of trades.data ?? []) if (!latest.has(t.symbol)) latest.set(t.symbol, t);

    if (!system) {
      const connected = {
        title: "V2 Discord alerts connected",
        description: "Discord is linked to V2 Decision Intelligence. Future messages are event-based and deduplicated.",
        fields: [
          { name: "Pairs", value: "EURUSD · GBPUSD", inline: true },
          { name: "Alerts", value: "Sweep/BOS/POI · paper trades · data trust · dual attention · model router", inline: false },
        ],
        footer: { text: "V2 research-only decision intelligence · not a live trading instruction" },
        timestamp: new Date().toISOString(),
      };
      const msg = await postDiscord([connected]);
      await log(null, [{ type: "connected", title: "connected", description: "connected" }], [connected], msg?.id ?? null);
      for (const pair of pairs) await saveState(`pair:${pair.symbol}`, snap(pair, latest.get(pair.symbol)));
      await saveState("_system", { connected: true }, true);
      return json({ ok: true, configured: true, bootstrap: true, sent: 1 });
    }

    const sent: any[] = [];
    for (const pair of pairs) {
      const key = `pair:${pair.symbol}`;
      const old = (await getState(key))?.snapshot ?? null;
      const trade = latest.get(pair.symbol) ?? null;
      const events = [trustEvent(pair, old), tradeEvent(trade, old), stageEvent(pair, old), modeEvent(pair, old), routerEvent(pair, old)].filter(Boolean) as Event[];
      if (events.length) {
        const embeds = events.map(e => embed(pair, e.title, e.description));
        const msg = await postDiscord(embeds);
        await log(pair.symbol, events, embeds, msg?.id ?? null);
        sent.push({ symbol: pair.symbol, events: events.map(e => e.type), messageId: msg?.id ?? null });
      }
      await saveState(key, snap(pair, trade), events.length > 0);
    }
    await saveState("_system", { connected: true, lastScanAt: new Date().toISOString() });
    return json({ ok: true, configured: true, generatedAt: new Date().toISOString(), sent });
  } catch (e) {
    console.error(e);
    return json({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
