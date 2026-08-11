-- V2 v2.0 historical metadata correction.
-- Reconstruct the earliest completed-M15 POI overlap for pre-v2.0 paper plans.
-- Descriptive backfill only: prospective flags and promotion evidence are unchanged.

with first_touches as (
  select p.trade_key,
         min(b.ts) as first_touch_at
  from public.paper_trades p
  join public.market_bars b
    on b.symbol = p.symbol
   and b.timeframe = '15m'
   and b.ts > p.bos_time
   and b.low <= p.poi_high + 0.000000001
   and b.high + 0.000000001 >= p.poi_low
  where p.armed_at < '2026-08-11T16:00:00Z'
  group by p.trade_key
), ranked as (
  select f.trade_key, f.first_touch_at,
         (select count(*)
            from public.market_bars b2
            join public.paper_trades p2 on p2.trade_key=f.trade_key
           where b2.symbol=p2.symbol
             and b2.timeframe='15m'
             and b2.ts > p2.bos_time
             and b2.ts <= f.first_touch_at) as first_touch_bar
  from first_touches f
)
update public.paper_trades p
set first_zone_touch_at = case
      when p.first_zone_touch_at is null then r.first_touch_at
      when r.first_touch_at < p.first_zone_touch_at then r.first_touch_at
      else p.first_zone_touch_at end,
    first_zone_touch_bar = case
      when p.first_zone_touch_at is null or r.first_touch_at < p.first_zone_touch_at then r.first_touch_bar
      else p.first_zone_touch_bar end,
    updated_at = now()
from ranked r
where p.trade_key=r.trade_key;

with z as (
  select p.trade_key,
         p.direction,
         p.poi_low,
         p.poi_high,
         p.first_zone_touch_at,
         b.low,
         b.high,
         greatest(
           0::numeric,
           case when p.direction='long'
             then (p.poi_high-b.low)/nullif(p.poi_high-p.poi_low,0)
             else (b.high-p.poi_low)/nullif(p.poi_high-p.poi_low,0)
           end
         ) as penetration
  from public.paper_trades p
  join public.market_bars b
    on b.symbol=p.symbol
   and b.timeframe='15m'
   and b.ts=p.first_zone_touch_at
  where p.armed_at < '2026-08-11T16:00:00Z'
)
update public.poi_penetration_events e
set reached_at=z.first_zone_touch_at,
    observed_penetration=z.penetration,
    age_bars=p.first_zone_touch_bar,
    before_midpoint=true,
    payload=coalesce(e.payload,'{}'::jsonb)||jsonb_build_object('v20_exact_edge_backfill',true)
from z
join public.paper_trades p on p.trade_key=z.trade_key
where e.trade_key=z.trade_key
  and e.threshold_pct=0
  and e.prospective=false;
