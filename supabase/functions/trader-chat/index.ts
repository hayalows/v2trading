const SB = Deno.env.get("SUPABASE_URL")!;
const H = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type",
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
};
const R = (x: unknown, status = 200) => new Response(JSON.stringify(x), { status, headers: H });
const n = (x: unknown) => Number.isFinite(Number(x)) ? Number(x) : null;
const price = (x: unknown) => n(x) == null ? "—" : Number(x).toFixed(5);
const signed = (x: unknown, d = 2) => n(x) == null ? "—" : `${Number(x) >= 0 ? "+" : ""}${Number(x).toFixed(d)}`;
const cap = (x: unknown) => String(x ?? "").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, m => m.toUpperCase());

type Pair = Record<string, any>;

function pairLine(p: Pair) {
  const t = p.trade;
  if (t?.status === "open") {
    return `${p.symbol}: ${String(t.direction).toUpperCase()} paper trade open at ${signed(t.currentR)}R. Entry ${price(t.entryPrice)}, stop ${price(t.stopPrice)}, target ${price(t.targetPrice)}. Current formation: ${p.formation?.plain?.title ?? p.formation?.label ?? "watching"}.`;
  }
  if (t?.status === "armed") {
    return `${p.symbol}: paper plan waiting for entry. ${p.formation?.plain?.title ?? "Market structure is still developing"}.`;
  }
  return `${p.symbol}: ${p.formation?.plain?.title ?? "No clean setup"}. Next: ${p.formation?.plain?.next ?? "wait for the next completed structural event"}.`;
}

function tradeAnswer(p: Pair) {
  const t = p.trade;
  if (!t) return `${p.symbol} has no active paper trade right now. ${p.formation?.plain?.summary ?? "V2 is still observing the setup."} Next: ${p.formation?.plain?.next ?? "wait for the next confirmed event"}.`;
  if (t.status === "armed") return `${p.symbol} has an armed ${String(t.direction).toUpperCase()} paper plan, but no entry has been recorded. Entry ${price(t.entryPrice)}, stop ${price(t.stopPrice)}, target ${price(t.targetPrice)}. ${t.copy ?? "V2 is waiting for the frozen entry rule."}`;
  return `${p.symbol} ${String(t.direction).toUpperCase()} paper trade is open at about ${signed(t.currentR)}R. Best seen ${signed(t.bestSeenR)}R, worst seen ${signed(t.worstSeenR)}R. Entry ${price(t.entryPrice)}, stop ${price(t.stopPrice)}, target ${price(t.targetPrice)}. The geometry stays frozen.`;
}

function macroAnswer(p: Pair) {
  const m = p.macro ?? {};
  const x = m.nextRelease;
  if (!x) return `${p.symbol}: no major scheduled release is in the immediate V2 event window. This only describes the app's current macro feed.`;
  const mins = Number(m.minutesToNext);
  const when = Number.isFinite(mins) ? mins < 60 ? `${Math.max(0, Math.round(mins))} minutes` : `${Math.max(0, Math.floor(mins / 60))}h ${Math.max(0, Math.round(mins % 60))}m` : "soon";
  return `${p.symbol}: ${x.title} is due in about ${when}. Event-risk level is ${m.level ?? "—"}. ${x.why ?? m.plain?.copy ?? "V2 treats this as a volatility warning, not a directional signal."}`;
}

function dataAnswer(p: Pair) {
  const d = p.status?.dataTrust ?? {};
  return `${p.symbol} data trust: ${d.level ?? "—"}${d.label ? ` (${d.label})` : ""}. ${d.reason ?? "No extra source warning is being surfaced."} V2 still has no broker execution truth, so paper fills are research approximations.`;
}

function modelAnswer(p: Pair) {
  const m = p.model ?? {};
  return `${p.symbol} model route: ${m.route ?? "ABSTAIN"}. Prospective evidence count: ${m.evidenceN ?? 0}. ${m.plain ?? "Model influence remains evidence-gated."}`;
}

function setupAnswer(p: Pair) {
  const f = p.formation ?? {}, plain = f.plain ?? {};
  return `${p.symbol}: ${plain.title ?? f.label ?? "Watching structure"}. ${plain.summary ?? "V2 is reading completed market structure."} Next: ${plain.next ?? "wait for the next completed structural event"}. Technical stage: ${plain.technicalLabel ?? `Stage ${f.stage ?? 0}/8`}.`;
}

function answer(brief: any, message: string, symbol?: string) {
  const pairs: Pair[] = Array.isArray(brief?.pairs) ? brief.pairs : [];
  const q = message.trim().toLowerCase();
  const explicit = String(symbol ?? "").toUpperCase();
  const wanted = explicit === "GBPUSD" || q.includes("gbpusd") || q.includes("gbp") ? "GBPUSD" : explicit === "EURUSD" || q.includes("eurusd") || q.includes("eur") ? "EURUSD" : "EURUSD";
  const both = q.includes("both") || q.includes("overview") || q.includes("what's happening") || q.includes("what is happening") || q.includes("going on") || q.includes("market now") || q.includes("all pairs");
  if (both) {
    const lines = pairs.map(pairLine).join("\n\n");
    return `${lines}\n\nThis is research state, not a broker execution instruction.`;
  }
  const p = pairs.find((x: Pair) => x.symbol === wanted) ?? pairs[0];
  if (!p) return "V2 could not load a current pair brief.";
  if (/(buy|sell|should i trade|take the trade|enter now|signal)/.test(q)) return `${setupAnswer(p)} ${tradeAnswer(p)} I can explain the research state, but V2 does not convert this into a live-money instruction.`;
  if (/(trade|entry|stop|sl\b|target|tp\b|open position|position)/.test(q)) return tradeAnswer(p);
  if (/(macro|news|event|cpi|fed|boe|rate|inflation)/.test(q)) return macroAnswer(p);
  if (/(data|trust|feed|source|quality|broker)/.test(q)) return dataAnswer(p);
  if (/(model|probability|ai|shadow|council|score)/.test(q)) return modelAnswer(p);
  if (/(next|setup|formation|stage|poi|bos|sweep|why)/.test(q)) return setupAnswer(p);
  return `${pairLine(p)}\n\nNext: ${p.status?.next ?? p.formation?.plain?.next ?? "wait for the next confirmed event"}. You can ask about the trade, setup, macro risk, data trust, or model evidence.`;
}

Deno.serve(async req => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: H });
  if (req.method !== "POST") return R({ error: "POST only" }, 405);
  try {
    const body = await req.json().catch(() => ({}));
    const message = String(body?.message ?? "").trim().slice(0, 800);
    if (!message) return R({ error: "message is required" }, 400);
    const r = await fetch(`${SB}/functions/v1/trader-brief`, { headers: { "Cache-Control": "no-cache" } });
    if (!r.ok) throw new Error(`trader-brief ${r.status}`);
    const brief = await r.json();
    const text = answer(brief, message, body?.symbol);
    return R({ answer: text, generatedAt: new Date().toISOString(), researchOnly: true });
  } catch (e) {
    console.error(e);
    return R({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
