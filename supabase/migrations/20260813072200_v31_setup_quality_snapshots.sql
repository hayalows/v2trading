-- V3.1 prospective setup-quality evidence.
-- Grades describe observed setup quality; they are not win probabilities and do not
-- alter entry, stop, target, dollar risk or trade status.

create table if not exists public.paper_trade_quality_snapshots (
  snapshot_key text primary key,
  trade_key text not null references public.paper_trades(trade_key) on delete cascade,
  symbol text not null,
  direction text not null,
  checkpoint text not null,
  observed_at timestamptz not null,
  prospective boolean not null,
  quality_grade text not null,
  plain_reason text not null,
  status text,
  setup_condition text,
  poi_lifecycle_state text,
  risk_pips numeric,
  risk_atr numeric,
  stop_policy_version text,
  context jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.paper_trade_quality_snapshots enable row level security;
revoke all on public.paper_trade_quality_snapshots from anon, authenticated;
grant all on public.paper_trade_quality_snapshots to service_role;
create index if not exists paper_trade_quality_snapshots_trade_idx on public.paper_trade_quality_snapshots(trade_key, observed_at);
create index if not exists paper_trade_quality_snapshots_prospective_idx on public.paper_trade_quality_snapshots(prospective, checkpoint, quality_grade);

create table if not exists public.v31_quality_release (
  release_id text primary key,
  release_at timestamptz not null
);
insert into public.v31_quality_release(release_id, release_at)
values ('v3.1', now())
on conflict (release_id) do nothing;
alter table public.v31_quality_release enable row level security;
revoke all on public.v31_quality_release from anon, authenticated;
grant all on public.v31_quality_release to service_role;

create or replace function public.v31_quality_label(p public.paper_trades, checkpoint_name text)
returns jsonb
language plpgsql
stable
set search_path = public
as $$
begin
  if p.status = 'invalid' or p.poi_lifecycle_state = 'invalidated_close_through' then
    return jsonb_build_object('grade','BROKEN','reason','The setup is no longer structurally valid.');
  end if;

  if checkpoint_name in ('first_touch','entry') then
    if p.setup_condition in ('partially_mitigated','partially_mitigated_after_target') then
      return jsonb_build_object('grade','WEAKENED','reason','Price touched the zone earlier before reaching the midpoint. Historical results were materially weaker after this kind of shallow first touch.');
    end if;
    if p.setup_condition = 'target_delivered_before_entry' then
      return jsonb_build_object('grade','LATE_RETURN','reason','The move had already travelled about 2.5R before returning to the entry. Treat this as a recycled move, not a fresh first interaction.');
    end if;
    if p.entry_at is not null and p.first_zone_touch_at is not null and date_trunc('minute',p.entry_at) = date_trunc('minute',p.first_zone_touch_at) then
      return jsonb_build_object('grade','STRONG_INTERACTION','reason','Price reached the midpoint on its first visit to the zone. This was the strongest early interaction pattern in the historical study.');
    end if;
    if checkpoint_name = 'entry' then
      return jsonb_build_object('grade','CLEAN_ENTRY','reason','The midpoint entry was reached without a recorded shallow-touch warning.');
    end if;
  end if;

  if p.first_zone_touch_at is not null and p.entry_at is null then
    return jsonb_build_object('grade','WATCH_TOUCH','reason','Price has started interacting with the zone, but the midpoint entry has not been reached yet.');
  end if;

  return jsonb_build_object('grade','WATCHING','reason','The setup is still forming. There is not enough interaction evidence yet to grade it as strong or weakened.');
end;
$$;

create or replace function public.v31_capture_quality_snapshots()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  release_at_ts timestamptz;
  q jsonb;
  observed timestamptz;
  cp text;
  cps text[] := array['armed'];
  final_status boolean;
begin
  select release_at into release_at_ts from public.v31_quality_release where release_id='v3.1';
  if new.first_zone_touch_at is not null then cps := array_append(cps,'first_touch'); end if;
  if new.entry_at is not null then cps := array_append(cps,'entry'); end if;
  final_status := new.status in ('win','loss','timeout','ambiguous','invalid');
  if final_status then cps := array_append(cps,'closed'); end if;

  foreach cp in array cps loop
    observed := case cp
      when 'armed' then new.armed_at
      when 'first_touch' then new.first_zone_touch_at
      when 'entry' then new.entry_at
      else coalesce(new.exit_at, new.updated_at, now())
    end;
    if observed is null then continue; end if;
    q := public.v31_quality_label(new, case when cp='closed' and new.entry_at is not null then 'entry' else cp end);
    insert into public.paper_trade_quality_snapshots(
      snapshot_key,trade_key,symbol,direction,checkpoint,observed_at,prospective,
      quality_grade,plain_reason,status,setup_condition,poi_lifecycle_state,risk_pips,risk_atr,stop_policy_version,context
    ) values (
      new.trade_key||':'||cp,new.trade_key,new.symbol,new.direction,cp,observed,
      observed >= release_at_ts,
      q->>'grade',q->>'reason',new.status,new.setup_condition,new.poi_lifecycle_state,
      new.risk_distance/0.0001,new.risk_atr,new.context->>'stop_policy_version',
      jsonb_build_object(
        'entry_price',new.entry_price,'stop_price',new.stop_price,'target_price',new.target_price,
        'first_zone_touch_at',new.first_zone_touch_at,'entry_at',new.entry_at,'exit_at',new.exit_at,
        'max_poi_penetration',new.max_poi_penetration,'bars_to_entry',new.bars_to_entry,
        'formation_stage',new.context->>'formation_stage','market_session',new.context->>'market_session'
      )
    ) on conflict (snapshot_key) do nothing;
  end loop;
  return new;
end;
$$;

drop trigger if exists trg_v31_capture_quality_snapshots on public.paper_trades;
create trigger trg_v31_capture_quality_snapshots
after insert or update on public.paper_trades
for each row execute function public.v31_capture_quality_snapshots();
