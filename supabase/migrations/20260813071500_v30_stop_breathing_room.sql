-- V3.0 prospective paper-stop policy.
-- Historical/previously armed plans are not rewritten. New EURUSD/GBPUSD rows keep
-- the structural sweep stop unless it is tighter than the researched minimum.

create or replace function public.v30_apply_stop_floor()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  floor_pips numeric;
  floor_distance numeric;
  structural_stop numeric;
  structural_risk numeric;
  adjusted_risk numeric;
  adjusted_risk_atr numeric;
  adjusted_valid boolean;
begin
  if new.symbol not in ('EURUSD','GBPUSD')
     or new.entry_price is null
     or new.stop_price is null
     or new.risk_distance is null
     or new.atr_at_plan is null
     or new.atr_at_plan <= 0
     or new.direction not in ('long','short') then
    return new;
  end if;

  floor_pips := case when new.symbol = 'EURUSD' then 4.0 else 5.0 end;
  floor_distance := floor_pips * 0.0001;
  structural_stop := new.stop_price;
  structural_risk := new.risk_distance;
  adjusted_risk := greatest(structural_risk, floor_distance);
  adjusted_risk_atr := adjusted_risk / new.atr_at_plan;
  adjusted_valid := adjusted_risk > 0 and adjusted_risk_atr >= 0.08 and adjusted_risk_atr <= 1.60;

  if new.direction = 'long' then
    new.stop_price := new.entry_price - adjusted_risk;
    new.target_price := new.entry_price + coalesce(new.reward_r, 2.5) * adjusted_risk;
  else
    new.stop_price := new.entry_price + adjusted_risk;
    new.target_price := new.entry_price - coalesce(new.reward_r, 2.5) * adjusted_risk;
  end if;

  new.risk_distance := adjusted_risk;
  new.risk_atr := adjusted_risk_atr;
  new.status := case when adjusted_valid then 'armed' else 'invalid' end;
  new.focus_active := adjusted_valid;
  new.context := coalesce(new.context, '{}'::jsonb) || jsonb_build_object(
    'stop_policy_version', 'v3.0_breathing_room',
    'stop_floor_pips', floor_pips,
    'stop_floor_applied', adjusted_risk > structural_risk + 0.000000000001,
    'structural_stop_price', structural_stop,
    'structural_risk_distance', structural_risk,
    'structural_risk_pips', structural_risk / 0.0001,
    'adjusted_risk_pips', adjusted_risk / 0.0001,
    'dollar_risk_rule', 'unchanged_1pct_at_entry',
    'position_size_effect', 'wider_stop_means_smaller_size',
    'research_source', 'V3.0 stop breathing-room study',
    'invalid_reason', case when adjusted_valid then null else format('adjusted risk_atr %.3s outside 0.08-1.60', adjusted_risk_atr::text) end
  );
  return new;
end;
$$;

drop trigger if exists trg_v30_apply_stop_floor on public.paper_trades;
create trigger trg_v30_apply_stop_floor
before insert on public.paper_trades
for each row execute function public.v30_apply_stop_floor();

create or replace function public.v30_sync_arm_event()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  p public.paper_trades%rowtype;
begin
  if new.event_type not in ('armed','invalid') then
    return new;
  end if;
  select * into p from public.paper_trades where trade_key = new.trade_key;
  if not found or coalesce(p.context->>'stop_policy_version','') <> 'v3.0_breathing_room' then
    return new;
  end if;

  new.event_type := case when p.status = 'armed' then 'armed' else 'invalid' end;
  new.price := case when p.status = 'armed' then p.entry_price else null end;
  new.payload := coalesce(new.payload, '{}'::jsonb) || jsonb_build_object(
    'entry', p.entry_price,
    'stop', p.stop_price,
    'target', p.target_price,
    'riskAtr', p.risk_atr,
    'riskPips', p.risk_distance / 0.0001,
    'stopFloorPips', (p.context->>'stop_floor_pips')::numeric,
    'stopFloorApplied', coalesce((p.context->>'stop_floor_applied')::boolean, false),
    'stopPolicyVersion', 'v3.0_breathing_room'
  );
  return new;
end;
$$;

drop trigger if exists trg_v30_sync_arm_event on public.paper_trade_events;
create trigger trg_v30_sync_arm_event
before insert on public.paper_trade_events
for each row execute function public.v30_sync_arm_event();
