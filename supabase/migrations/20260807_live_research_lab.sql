create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

create table if not exists public.instruments (
  symbol text primary key,
  name text not null,
  asset_class text not null,
  chart_symbol text not null,
  chart_source text not null default 'Yahoo Finance public chart',
  quote_symbol text,
  quote_source text,
  role text not null default 'research_reference',
  proxy_disclaimer text,
  sort_order integer not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

insert into public.instruments(symbol,name,asset_class,chart_symbol,quote_symbol,quote_source,role,proxy_disclaimer,sort_order) values
('EURUSD','Euro / U.S. Dollar','forex','EURUSD=X','EUR/USD','exchangerate.dev + Yahoo','research_reference','Public reference feed. Not broker execution truth.',1),
('GBPUSD','British Pound / U.S. Dollar','forex','GBPUSD=X','GBP/USD','exchangerate.dev + Yahoo','research_reference','Public reference feed. Not broker execution truth.',2),
('XAUUSD','Gold / U.S. Dollar','metals','GC=F','XAU/USD','goldprice.dev + Yahoo','context_proxy','COMEX gold futures are used as a free structure proxy; anonymous spot XAU reference is used when available.',3),
('US30','Dow / US30','index_cfd','YM=F','US30','Yahoo','context_proxy','E-mini Dow futures are used as a free extended-hours context proxy for a broker US30 CFD.',4)
on conflict (symbol) do update set
  name=excluded.name,asset_class=excluded.asset_class,chart_symbol=excluded.chart_symbol,
  quote_symbol=excluded.quote_symbol,quote_source=excluded.quote_source,role=excluded.role,
  proxy_disclaimer=excluded.proxy_disclaimer,sort_order=excluded.sort_order,active=true;

create table if not exists public.provider_cache (
  cache_key text primary key,
  payload jsonb not null,
  fetched_at timestamptz not null default now(),
  expires_at timestamptz not null,
  status text not null default 'ok',
  error text
);

create table if not exists public.market_bars (
  symbol text not null references public.instruments(symbol) on delete cascade,
  timeframe text not null check (timeframe in ('15m','1h','4h','1d')),
  ts timestamptz not null,
  open double precision not null,
  high double precision not null,
  low double precision not null,
  close double precision not null,
  volume double precision,
  source text not null,
  is_proxy boolean not null default false,
  inserted_at timestamptz not null default now(),
  primary key(symbol,timeframe,ts,source)
);
create index if not exists market_bars_symbol_tf_ts_idx on public.market_bars(symbol,timeframe,ts desc);

create table if not exists public.market_states (
  symbol text primary key references public.instruments(symbol) on delete cascade,
  as_of timestamptz not null,
  reference_price double precision,
  bid double precision,
  ask double precision,
  spread double precision,
  quote_source text,
  chart_source text not null,
  market_session text,
  d1_trend text,h4_trend text,h1_trend text,m15_trend text,
  d1_strength double precision,h4_strength double precision,h1_strength double precision,m15_strength double precision,
  regime text,
  formation_stage integer not null default 0 check (formation_stage between 0 and 8),
  formation_code text not null default 'NO_SETUP',
  formation_label text not null default 'No active V2 formation',
  formation_direction text,
  formation_confidence double precision,
  atr15 double precision,
  range_position double precision,
  prev_day_high double precision,prev_day_low double precision,
  swing_high double precision,swing_low double precision,
  poi_high double precision,poi_low double precision,
  distance_to_poi_atr double precision,
  research_summary text,
  data_health jsonb not null default '{}'::jsonb,
  details jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.market_state_history (
  id bigint generated always as identity primary key,
  symbol text not null references public.instruments(symbol) on delete cascade,
  as_of timestamptz not null,
  reference_price double precision,
  formation_stage integer not null,
  formation_code text not null,
  formation_direction text,
  regime text,
  state jsonb not null,
  created_at timestamptz not null default now()
);
create index if not exists market_state_history_symbol_asof_idx on public.market_state_history(symbol,as_of desc);

alter table public.instruments enable row level security;
alter table public.provider_cache enable row level security;
alter table public.market_bars enable row level security;
alter table public.market_states enable row level security;
alter table public.market_state_history enable row level security;

drop policy if exists instruments_public_read on public.instruments;
drop policy if exists provider_cache_service_role_all on public.provider_cache;
drop policy if exists market_bars_public_read on public.market_bars;
drop policy if exists market_states_public_read on public.market_states;
drop policy if exists market_state_history_public_read on public.market_state_history;
create policy instruments_public_read on public.instruments for select using (true);
create policy provider_cache_service_role_all on public.provider_cache for all to service_role using (true) with check (true);
create policy market_bars_public_read on public.market_bars for select using (true);
create policy market_states_public_read on public.market_states for select using (true);
create policy market_state_history_public_read on public.market_state_history for select using (true);

grant select on public.instruments,public.market_bars,public.market_states,public.market_state_history to anon,authenticated;
grant all privileges on public.instruments,public.provider_cache,public.market_bars,public.market_states,public.market_state_history to service_role;
grant usage,select on all sequences in schema public to service_role;

-- This event-trigger helper is installed in some Supabase projects. It should not be callable as a public RPC.
do $$ begin
  if to_regprocedure('public.rls_auto_enable()') is not null then
    revoke execute on function public.rls_auto_enable() from public,anon,authenticated;
  end if;
end $$;

-- The production project schedules this separately after the Edge Function exists:
-- select cron.schedule('v2-market-lab-refresh-5m','*/5 * * * *',
--   $$select net.http_get(url := 'https://<project-ref>.supabase.co/functions/v1/market-lab?symbol=all');$$);
