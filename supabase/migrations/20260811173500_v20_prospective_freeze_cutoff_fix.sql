-- V2 v2.0 hotfix: prospective eligibility is based on when the plan geometry was frozen.
-- Yahoo/M15 timestamps represent bar starts. If BOS is at T, the first eligible
-- future bar starts at T+15m and completes at T+30m. A plan frozen before T+30m
-- is therefore pre-outcome for the first eligible entry bar.

create or replace function public.v20_freeze_is_prospective(p_trade_key text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (
      select
        pt.armed_at >= timestamptz '2026-08-11 16:00:00+00'
        and pt.armed_at < pt.bos_time + interval '30 minutes'
        and coalesce((pt.context->>'recovered_from_history')::boolean, false) = false
      from public.paper_trades pt
      where pt.trade_key = p_trade_key
    ),
    false
  );
$$;

revoke all on function public.v20_freeze_is_prospective(text) from public, anon, authenticated;
grant execute on function public.v20_freeze_is_prospective(text) to service_role;

create or replace function public.v20_force_shadow_prospective_flag()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  new.prospective := public.v20_freeze_is_prospective(new.trade_key);
  return new;
end;
$$;

revoke all on function public.v20_force_shadow_prospective_flag() from public, anon, authenticated;
grant execute on function public.v20_force_shadow_prospective_flag() to service_role;

drop trigger if exists v20_depth_shadow_prospective_guard on public.poi_depth_shadow;
create trigger v20_depth_shadow_prospective_guard
before insert or update of trade_key, prospective
on public.poi_depth_shadow
for each row execute function public.v20_force_shadow_prospective_flag();

drop trigger if exists v20_penetration_prospective_guard on public.poi_penetration_events;
create trigger v20_penetration_prospective_guard
before insert or update of trade_key, prospective
on public.poi_penetration_events
for each row execute function public.v20_force_shadow_prospective_flag();

-- Reclassify only rows whose plan was genuinely frozen before the first eligible
-- future M15 bar could complete. This does not alter any price/outcome fields.
update public.poi_depth_shadow s
set prospective = public.v20_freeze_is_prospective(s.trade_key),
    updated_at = now()
where s.prospective is distinct from public.v20_freeze_is_prospective(s.trade_key);

update public.poi_penetration_events e
set prospective = public.v20_freeze_is_prospective(e.trade_key)
where e.prospective is distinct from public.v20_freeze_is_prospective(e.trade_key);
