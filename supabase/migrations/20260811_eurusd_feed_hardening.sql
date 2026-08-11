-- EURUSD feed hardening after Yahoo EURUSD intraday quantization audit.
-- Canonical policy: Dukascopy BID history + Twelve Data UTC 1m live tail,
-- with fail-closed health gates and database-level circuit breakers.

alter table public.market_bars drop constraint if exists market_bars_timeframe_check;
alter table public.market_bars add constraint market_bars_timeframe_check
  check (timeframe = any (array['5m'::text,'15m'::text,'1h'::text,'4h'::text,'1d'::text]));

create table if not exists public.market_raw_bars (
  symbol text not null,
  timeframe text not null check (timeframe = any (array['1m'::text,'5m'::text,'15m'::text,'1h'::text,'4h'::text,'1d'::text])),
  ts timestamptz not null,
  open double precision not null,
  high double precision not null,
  low double precision not null,
  close double precision not null,
  volume double precision,
  source text not null,
  inserted_at timestamptz not null default now(),
  primary key (symbol,timeframe,ts,source)
);
create index if not exists market_raw_bars_symbol_tf_ts_idx on public.market_raw_bars(symbol,timeframe,ts desc);
alter table public.market_raw_bars enable row level security;
grant select,insert,update,delete on public.market_raw_bars to service_role;
revoke all on public.market_raw_bars from anon, authenticated;

create or replace function public.block_deprecated_eurusd_yahoo_m15()
returns trigger language plpgsql as $$
begin
  if new.symbol='EURUSD' and new.timeframe='15m' and new.source='Yahoo Finance public chart'
     and new.ts >= timestamptz '2026-08-10 13:00:00+00' then
    return null;
  end if;
  return new;
end;
$$;
drop trigger if exists trg_block_deprecated_eurusd_yahoo_m15 on public.market_bars;
create trigger trg_block_deprecated_eurusd_yahoo_m15
before insert or update on public.market_bars
for each row execute function public.block_deprecated_eurusd_yahoo_m15();

create or replace function public.v2_market_state_data_health_guard()
returns trigger language plpgsql as $$
declare
  dh jsonb := coalesce(new.data_health, '{}'::jsonb);
  lag_bars integer := coalesce(nullif(dh->>'structureLagBars','')::integer, 0);
  gap_count integer := coalesce(nullif(dh->>'gapCount96','')::integer, 0);
  dup_count integer := coalesce(nullif(dh->>'duplicateCount96','')::integer, 0);
  explicitly_usable text := dh->>'structureUsable';
  quantized text := dh->'resolution'->>'quantized';
  blocked boolean;
  reason text;
begin
  if new.symbol='EURUSD'
     and now() >= timestamptz '2026-08-11 18:30:00+00'
     and coalesce(new.chart_source,'') <> 'EURUSD canonical structure v1' then
    if tg_op='UPDATE' and old.chart_source='EURUSD canonical structure v1' then
      return old;
    end if;
    new.formation_stage := 0;
    new.formation_code := 'DATA_DEGRADED';
    new.formation_label := 'Structure withheld — deprecated EURUSD source blocked';
    new.formation_direction := null;
    new.formation_confidence := 0;
    new.poi_high := null;
    new.poi_low := null;
    new.distance_to_poi_atr := null;
    new.data_health := dh || jsonb_build_object(
      'structureUsable',false,
      'blockedReason','Structure withheld — deprecated EURUSD source blocked',
      'circuitBreaker',true,
      'deprecatedSourceBlocked',new.chart_source
    );
    return new;
  end if;

  blocked := new.formation_code='DATA_DEGRADED'
    or explicitly_usable='false'
    or quantized='true'
    or lag_bars>0
    or gap_count>0
    or dup_count>0;

  if blocked then
    reason := case
      when explicitly_usable='false' and coalesce(dh->>'blockedReason','')<>'' then dh->>'blockedReason'
      when quantized='true' then 'Structure withheld — quantized price feed'
      when lag_bars>0 then format('Structure withheld — feed %s bar(s) behind',lag_bars)
      when gap_count>0 then format('Structure withheld — %s recent M15 gap(s)',gap_count)
      when dup_count>0 then format('Structure withheld — %s duplicate M15 bar(s)',dup_count)
      else 'Structure withheld — data quality gate'
    end;
    new.formation_stage := 0;
    new.formation_code := 'DATA_DEGRADED';
    new.formation_label := reason;
    new.formation_direction := null;
    new.formation_confidence := 0;
    new.poi_high := null;
    new.poi_low := null;
    new.distance_to_poi_atr := null;
    new.data_health := dh || jsonb_build_object('structureUsable',false,'blockedReason',reason,'circuitBreaker',true);
    new.details := coalesce(new.details,'{}'::jsonb) || jsonb_build_object(
      'formation',jsonb_build_object('blocked',true,'reason',reason),
      'dataQualityCircuitBreaker',true
    );
  end if;
  return new;
end;
$$;
drop trigger if exists trg_v2_market_state_data_health_guard on public.market_states;
create trigger trg_v2_market_state_data_health_guard
before insert or update on public.market_states
for each row execute function public.v2_market_state_data_health_guard();

create or replace function public.v2_suppress_unhealthy_state_history()
returns trigger language plpgsql as $$
declare
  dh jsonb := coalesce(new.state->'dataHealth', '{}'::jsonb);
  lag_bars integer := coalesce(nullif(dh->>'structureLagBars','')::integer, 0);
  gap_count integer := coalesce(nullif(dh->>'gapCount96','')::integer, 0);
  dup_count integer := coalesce(nullif(dh->>'duplicateCount96','')::integer, 0);
  source_name text := coalesce(dh->>'structureSource','');
begin
  if new.symbol='EURUSD'
     and new.as_of >= timestamptz '2026-08-11 18:30:00+00'
     and source_name <> 'EURUSD canonical structure v1' then
    return null;
  end if;
  if new.formation_code='DATA_DEGRADED'
     or dh->>'structureUsable'='false'
     or dh->'resolution'->>'quantized'='true'
     or lag_bars>0
     or gap_count>0
     or dup_count>0 then
    return null;
  end if;
  return new;
end;
$$;
drop trigger if exists aaa_v2_suppress_unhealthy_state_history on public.market_state_history;
create trigger aaa_v2_suppress_unhealthy_state_history
before insert on public.market_state_history
for each row execute function public.v2_suppress_unhealthy_state_history();

create or replace function public.v2_eurusd_paper_arm_source_guard()
returns trigger language plpgsql as $$
declare
  s public.market_states%rowtype;
  healthy boolean := false;
  fresh boolean := false;
begin
  if new.symbol<>'EURUSD' or new.armed_at<timestamptz '2026-08-11 18:30:00+00' or new.status<>'armed' then
    return new;
  end if;
  select * into s from public.market_states where symbol='EURUSD';
  healthy := found
    and s.chart_source='EURUSD canonical structure v1'
    and coalesce((s.data_health->>'structureUsable')::boolean,false)
    and coalesce((s.data_health->>'structureLagBars')::integer,999)=0
    and coalesce((s.data_health->>'gapCount96')::integer,999)=0
    and coalesce((s.data_health->>'duplicateCount96')::integer,999)=0;
  fresh := found and s.updated_at>=now()-interval '6 minutes';
  if not healthy or not fresh then
    new.status := 'invalid';
    new.focus_active := false;
    new.context := coalesce(new.context,'{}'::jsonb) || jsonb_build_object(
      'source_guard','blocked_unhealthy_or_stale_eurusd_structure',
      'source_guard_at',now(),
      'source_guard_chart_source',s.chart_source,
      'source_guard_state_updated_at',s.updated_at,
      'source_guard_health',s.data_health
    );
  else
    new.context := coalesce(new.context,'{}'::jsonb) || jsonb_build_object(
      'source_guard','passed_canonical_eurusd_structure',
      'source_guard_at',now(),
      'source_guard_state_updated_at',s.updated_at
    );
  end if;
  return new;
end;
$$;
drop trigger if exists trg_v2_eurusd_paper_arm_source_guard on public.paper_trades;
create trigger trg_v2_eurusd_paper_arm_source_guard
before insert on public.paper_trades
for each row execute function public.v2_eurusd_paper_arm_source_guard();

create or replace function public.v2_censor_legacy_eurusd_5m_paper_resolution()
returns trigger language plpgsql as $$
begin
  if new.symbol='EURUSD'
     and new.armed_at>=timestamptz '2026-08-11 18:30:00+00'
     and new.resolution_timeframe='5m' then
    new.status := 'ambiguous';
    new.lifecycle_phase := 'closed';
    new.focus_active := false;
    new.gross_r := null;
    new.exit_price := null;
    new.exit_at := coalesce(new.exit_at,new.entry_at,now());
    new.ambiguous_reason := 'Legacy Yahoo EURUSD 5m resolution censored; canonical 5m verification required';
    new.context := coalesce(new.context,'{}'::jsonb) || jsonb_build_object(
      'legacy_eurusd_5m_censored',true,
      'canonical_5m_verified',false,
      'canonical_5m_required_since','2026-08-11T18:30:00Z'
    );
  end if;
  return new;
end;
$$;
drop trigger if exists zz_v2_censor_legacy_eurusd_5m_paper_resolution on public.paper_trades;
create trigger zz_v2_censor_legacy_eurusd_5m_paper_resolution
before update on public.paper_trades
for each row execute function public.v2_censor_legacy_eurusd_5m_paper_resolution();

create or replace function public.v2_guard_blocked_paper_events()
returns trigger language plpgsql as $$
declare
  ctx jsonb;
  original_type text := new.event_type;
begin
  select context into ctx from public.paper_trades where trade_key=new.trade_key;
  if ctx->>'source_guard'='blocked_unhealthy_or_stale_eurusd_structure' then
    if new.event_type in ('armed','entry','win','loss','timeout') then
      new.event_type := 'invalid';
      new.price := null;
      new.payload := coalesce(new.payload,'{}'::jsonb) || jsonb_build_object('source_guard',ctx->>'source_guard','original_event_type',original_type);
    end if;
    return new;
  end if;
  if ctx->>'legacy_eurusd_5m_censored'='true' and new.event_type in ('entry','win','loss','timeout') then
    new.event_type := 'ambiguous';
    new.price := null;
    new.payload := coalesce(new.payload,'{}'::jsonb) || jsonb_build_object(
      'canonical_5m_verification_required',true,
      'original_event_type',original_type,
      'reason','Legacy Yahoo EURUSD 5m resolution censored after feed audit'
    );
  end if;
  return new;
end;
$$;
drop trigger if exists trg_v2_guard_blocked_paper_events on public.paper_trade_events;
create trigger trg_v2_guard_blocked_paper_events
before insert on public.paper_trade_events
for each row execute function public.v2_guard_blocked_paper_events();

create or replace function public.v2_guard_blocked_depth_shadow()
returns trigger language plpgsql as $$
declare
  ctx jsonb;
  parent_armed_at timestamptz;
begin
  select context,armed_at into ctx,parent_armed_at from public.paper_trades where trade_key=new.trade_key;
  if ctx->>'source_guard'='blocked_unhealthy_or_stale_eurusd_structure' then
    new.prospective := false;
    new.eligible := false;
    new.status := 'ineligible';
    new.gross_r := null;
    new.ambiguous_reason := 'Parent plan blocked by EURUSD source-health guard';
    return new;
  end if;
  if new.symbol='EURUSD'
     and parent_armed_at>=timestamptz '2026-08-11 18:30:00+00'
     and new.resolution_timeframe='5m' then
    new.status := 'ambiguous';
    new.gross_r := null;
    new.exit_price := null;
    new.ambiguous_reason := 'Legacy Yahoo EURUSD 5m resolution censored; canonical 5m verification required';
  end if;
  return new;
end;
$$;
drop trigger if exists zz_v2_guard_blocked_depth_shadow on public.poi_depth_shadow;
create trigger zz_v2_guard_blocked_depth_shadow
before insert or update on public.poi_depth_shadow
for each row execute function public.v2_guard_blocked_depth_shadow();

create or replace function public.v2_eurusd_feed_watchdog()
returns void language plpgsql security definer set search_path=public as $$
declare
  s public.market_states%rowtype;
  reason text;
begin
  select * into s from public.market_states where symbol='EURUSD' for update;
  if not found then return; end if;
  if s.chart_source<>'EURUSD canonical structure v1' or s.updated_at<now()-interval '6 minutes' then
    reason := case when s.chart_source<>'EURUSD canonical structure v1'
      then 'Structure withheld — canonical EURUSD source unavailable'
      else 'Structure withheld — canonical EURUSD refresh is stale' end;
    update public.market_states
    set formation_stage=0,formation_code='DATA_DEGRADED',formation_label=reason,
        formation_direction=null,formation_confidence=0,poi_high=null,poi_low=null,distance_to_poi_atr=null,
        research_summary='EURUSD: '||reason||'. No new formation or paper plan may be armed.',
        data_health=coalesce(data_health,'{}'::jsonb)||jsonb_build_object('structureUsable',false,'blockedReason',reason,'watchdog',true,'watchdogAt',now()),
        details=coalesce(details,'{}'::jsonb)||jsonb_build_object('dataQualityCircuitBreaker',true)
    where symbol='EURUSD';
  end if;
end;
$$;

-- Keep the legacy market-lab scheduler on GBPUSD only.
do $legacy_job$
declare j bigint;
begin
  select jobid into j from cron.job where jobname='v2-market-lab-refresh-5m' limit 1;
  if j is not null then
    perform cron.alter_job(j, command := $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/market-lab?symbol=GBPUSD');$$);
  end if;
end
$legacy_job$;

-- Recreate named jobs idempotently.
do $jobs$
declare j bigint;
begin
  for j in select jobid from cron.job where jobname in (
    'v2-eurusd-fast-canonical','v2-eurusd-duka-raw-sync','v2-eurusd-feed-watchdog','v2-eurusd-canonical-5m-verifier'
  ) loop
    perform cron.unschedule(j);
  end loop;
end
$jobs$;

select cron.schedule('v2-eurusd-fast-canonical','1-56/5 * * * *',
  $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/eurusd-market-lab', timeout_milliseconds := 8000);$$);
select cron.schedule('v2-eurusd-duka-raw-sync','7 * * * *',
  $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/dukascopy-raw-sync', timeout_milliseconds := 20000);$$);
select cron.schedule('v2-eurusd-feed-watchdog','0-55/5 * * * *',
  $$select public.v2_eurusd_feed_watchdog();$$);
select cron.schedule('v2-eurusd-canonical-5m-verifier','4-59/5 * * * *',
  $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/eurusd-canonical-5m-verifier', timeout_milliseconds := 8000);$$);
