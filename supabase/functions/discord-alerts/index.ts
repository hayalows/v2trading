import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const DISCORD_WEBHOOK_URL = Deno.env.get("DISCORD_WEBHOOK_URL") ?? "";
const db = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });
const CORE = ["EURUSD", "GBPUSD"];
const STAGE_ALERTS = new Set([3, 5, 6, 7, 8]);
const RESULT_STATUSES = new Set(["win", "loss", "timeout", "ambiguous", "expired", "invalid"]);
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Cache-Control": "no-store",
};

const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" },
});

const fmt = (v: unknown, digits = 5) => Number.isFinite(Number(v)) ? Number(v).toFixed(digits) : "—";
const upper = (v: unknown) => String(v ?? "—").toUpperCase();
const asIso = (v: unknown) => v ? new Date(String(v)).toISOString() : null;

function validWebhook(url: string) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" && u.hostname === "discord.com" && u.pathname.startsWith("/api/webhooks/");
  } catch {
    return false;
  }
}

function snapshot(pair: any, trade: any) {
  return {
    campaignKey: pair?.campaign?.campaign_key ?? null,
    stage: Number(pair?.formation?.stage ?? 0),
    direction: pair?.formation?.direction ?? null,
    decisionMode: pair?.decision?.mode ?? null,
    dataTrust: pair?.decision?.dataTrust?.level ?? null,
    router: pair?.decision?.router?.route ?? "ABSTAIN",
    tradeKey: trade?.trade_key ?? null,
    tradeStatus: trade?.status ?? null,
    tradeUpdatedAt: trade?.updated_at ?? null,
  };
}

function baseEmbed(pair: any, title: string, description: string) {
  const f = pair?.formation ?? {};
  const d = pair?.decision ?? {};
  return {
    title: `${pair.symbol} · ${title}`,
    description,
    fields: [
      { name: "Formation", value: `${upper(f.direction)} · Stage ${Number(f.stage ?? 0)}/8`, inline: true },
      { name: "Decision", value: String(d.mode ?? "—"), inline: true },
      { name: "Data", value: String(d.dataTrust?.level ?? "—"), inline: true },
      { name: "Model", value: String(d.router?.route ?? "ABSTAIN"), inline: true },
      { name: "Price", value: fmt(pair?.referencePrice), inline: true },
      { name: "As of", value: asIso(pair?.asOf)?.replace("T", " ").replace(".000Z", " UTC") ?? "—", inline: true },
    ],
    footer: { text: "V2 research-only decision intelligence · not a live trading instruction" },
    timestamp: new Date().toISOString(),
  };
}

function stageEvent(pair: any, prev: any) {
  const s = Number(pair?.formation?.stage ?? 0);
  const campaign = pair?.campaign?.campaign_key ?? null;
  const changed = !prev || prev.campaignKey !== campaign || prev.stage !== s || prev.direction !== pair?.formation?.direction;
  if (!changed || !STAGE_ALERTS.has(s)) return null;
  const map: Record<number, [string, string]> = {
    3: ["Sweep confirmed", "A clean liquidity sweep has been recorded. V2 is now waiting for same-direction BOS."],
    5: ["BOS confirmed", "Break of structure is confirmed on completed M15 data. Fresh POI identification is next."],
    6: ["Fresh POI identified", `A fresh POI has been frozen. Baseline midpoint remains 50%. POI: ${fmt(pair?.formation?.poiLow)}–${fmt(pair?.formation?.poiHigh)}.`],
    7: ["Approaching POI", `Price is approaching the frozen research POI. Distance: ${fmt(pair?.formation?.distanceToPoiAtr, 2)} ATR.`],
    8: ["Entry zone reached", "The frozen research entry zone has been reached. This is a paper-research event, not a broker instruction."],
  };
  const [title, description] = map[s];
  return { type: `stage_${s}`, title, description };
}

function tradeEvent(trade: any, prev: any) {
  if (!trade) return null;
  const isNew = !prev?.tradeKey || prev.tradeKey !== trade.trade_key;
  const statusChanged = isNew || prev.tradeStatus !== trade.status || prev.tradeUpdatedAt !== trade.updated_at;
  if (!statusChanged) return null;
  if (trade.status === "armed") return {
    type: "paper_armed",
    title: "Paper plan armed",
    description: `${upper(trade.direction)} research plan armed. Entry ${fmt(trade.entry_price)} · Stop ${fmt(trade.stop_price)} · Target ${fmt(trade.target_price)} · Risk ${fmt(trade.risk_atr, 2)} ATR.`,
  };
  if (trade.status === "open") return {
    type: "paper_open",
    title: "Paper entry recorded",
    description: `${upper(trade.direction)} paper entry recorded at ${fmt(trade.entry_price)}. Frozen stop ${fmt(trade.stop_price)} · target ${fmt(trade.target_price)}.`,
  };
  if (RESULT_STATUSES.has(trade.status)) return {
    type: `paper_${trade.status}`,
    title: `Paper trade ${upper(trade.status)}`,
    description: `${upper(trade.direction)} paper trade resolved ${upper(trade.status)}${Number.isFinite(Number(trade.gross_r)) ? ` · ${Number(trade.gross_r).toFixed(2)}R` : ""}${Number.isFinite(Number(trade.exit_price)) ? ` · exit ${fmt(trade.exit_price)}` : ""}.`,
  };
  return null;
}

function trustEvent(pair: any, prev: any) {
  const now = pair?.decision?.dataTrust?.level ?? null;
  const old = prev?.dataTrust ?? null;
  if (!old || old === now) return null;
  if (now === "BLOCKED") return { type: "data_blocked", title: "Data blocked", description: `V2 stopped formation/model influence for this pair because a structure-quality gate failed. ${pair?.decision?.dataTrust?.reason ?? ""}` };
  if (old === "BLOCKED") return { type: "data_restored", title: "Data restored", description: `The structure feed has recovered to ${now}. V2 can resume research-state tracking.` };
  return null;
}

function modeEvent(pair: any, prev: any) {
  const now = pair?.decision?.mode ?? null;
  if (now === "DUAL_ATTENTION" && prev?.decisionMode !== "DUAL_ATTENTION") {
    return { type: "dual_attention", title: "Dual attention", description: "An existing paper plan/trade and a new opposite-direction formation coexist. They remain independent; V2 will not auto-reverse the existing paper trade." };
  }
  return null;
}

function routerEvent(pair: any, prev: any) {
  const now = pair?.decision?.router?.route ?? "ABSTAIN";
  const old = prev?.router ?? null;
  if (!old || old === now) return null;
  if (now === "ABSTAIN") return { type: "router_abstain", title: "Model router abstaining", description: "Prospective model evidence no longer clears the routing gate. Structural engine remains primary." };
  return { type: "router_active", title: `Model router → ${now}`, description: `${now} has cleared the prospective routing gate in the current evidence scope. Raw probabilities remain hidden.` };
}

async function sendDiscord(embed: any) {
  const u = new URL(DISCORD_WEBHOOK_URL);
  u.searchParams.set("wait", "true");
  const res = await fetch(u.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: "V2 Decision Intelligence",
      allowed_mentions: { parse: [] },
      embeds: [embed],
    }),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`Discord ${res.status}: ${text.slice(0, 300)}`);
  try { return JSON.parse(text); } catch { return { id: null }; }
}

async function getState(key: string) {
  const { data, error } = await db.from("discord_alert_state").select("snapshot,updated_at,last_sent_at").eq("state_key", key).maybeSingle();
  if (error) throw new Error(error.message);
  return data;
}

async function saveState(key: string, snap: any, sent = false) {
  const row: any = { state_key: key, snapshot: snap, updated_at: new Date().toISOString() };
  if (sent) row.last_sent_at = new Date().toISOString();
  const { error } = await db.from("discord_alert_state").upsert(row, { onConflict: "state_key" });
  if (error) throw new Error(error.message);
}

async function logAlert(symbol: string | null, eventType: string, embed: any, message: any) {
  const { error } = await db.from("discord_alert_log").insert({
    symbol,
    event_type: eventType,
    discord_message_id: message?.id ?? null,
    payload: embed,
    sent_at: new Date().toISOString(),
  });
  if (error) console.error("alert log write failed", error.message);
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "GET") return reply({ error: "GET only" }, 405);
  try {
    if (!validWebhook(DISCORD_WEBHOOK_URL)) return reply({ configured: false, reason: "DISCORD_WEBHOOK_URL is not configured with an official Discord incoming webhook URL." }, 503);

    const system = await getState("_system");
    if (system?.updated_at && Date.now() - Date.parse(system.updated_at) < 210_000) {
      return reply({ ok: true, configured: true, skipped: "throttled", nextUsefulRunSeconds: 210 });
    }

    const [intelRes, tradesRes] = await Promise.all([
      fetch(`${SUPABASE_URL}/functions/v1/decision-intelligence`, { headers: { "Cache-Control": "no-cache" } }),
      db.from("paper_trades").select("trade_key,symbol,direction,status,entry_price,stop_price,target_price,risk_atr,entry_at,exit_at,exit_price,gross_r,updated_at,armed_at").in("symbol", CORE).order("armed_at", { ascending: false }).limit(20),
    ]);
    if (!intelRes.ok) throw new Error(`decision-intelligence ${intelRes.status}`);
    if (tradesRes.error) throw new Error(tradesRes.error.message);
    const intel = await intelRes.json();
    const pairs = Array.isArray(intel?.pairs) ? intel.pairs : [];
    const latestTrade = new Map<string, any>();
    for (const t of tradesRes.data ?? []) if (!latestTrade.has(t.symbol)) latestTrade.set(t.symbol, t);

    if (!system) {
      const embed = {
        title: "V2 Discord alerts connected",
        description: "Discord is now linked to V2 Decision Intelligence. Future messages will be event-based and deduplicated.",
        fields: [
          { name: "Pairs", value: "EURUSD · GBPUSD", inline: true },
          { name: "Alerts", value: "Sweep/BOS/POI · paper trades · data trust · dual attention · model router", inline: false },
        ],
        footer: { text: "V2 research-only decision intelligence · not a live trading instruction" },
        timestamp: new Date().toISOString(),
      };
      const msg = await sendDiscord(embed);
      await logAlert(null, "connected", embed, msg);
      for (const pair of pairs) await saveState(`pair:${pair.symbol}`, snapshot(pair, latestTrade.get(pair.symbol)), false);
      await saveState("_system", { connected: true }, true);
      return reply({ ok: true, configured: true, bootstrap: true, sent: 1 });
    }

    const sent: any[] = [];
    for (const pair of pairs) {
      const key = `pair:${pair.symbol}`;
      const oldRow = await getState(key);
      const prev = oldRow?.snapshot ?? null;
      const trade = latestTrade.get(pair.symbol) ?? null;
      const candidates = [
        trustEvent(pair, prev),
        tradeEvent(trade, prev),
        stageEvent(pair, prev),
        modeEvent(pair, prev),
        routerEvent(pair, prev),
      ].filter(Boolean) as any[];

      let allSent = true;
      for (const event of candidates) {
        const embed = baseEmbed(pair, event.title, event.description);
        const msg = await sendDiscord(embed);
        await logAlert(pair.symbol, event.type, embed, msg);
        sent.push({ symbol: pair.symbol, type: event.type, messageId: msg?.id ?? null });
      }
      if (!allSent) continue;
      await saveState(key, snapshot(pair, trade), candidates.length > 0);
    }
    await saveState("_system", { connected: true, lastScanAt: new Date().toISOString() }, false);
    return reply({ ok: true, configured: true, generatedAt: new Date().toISOString(), sent });
  } catch (e) {
    console.error(e);
    return reply({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
