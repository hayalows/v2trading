-- V2 v2.0: prospective POI lifecycle + depth learning.
-- Research only. The production baseline paper entry remains the 50% midpoint.

alter table public.paper_trades
  add column if not exists poi_lifecycle_state text not null default 'untouched',
  add column if not exists max_poi_penetration numeric not null default 0,
  add column if not exists max_poi_penetration_at timestamptz,
  add column if not exists distal_close_at timestamptz,
  add column if not exists focus_active boolean not null default true,
  add column if not exists focus_suppression_reason text,
  add column if not exists superseded_by_trade_key text;

alter table public.paper_trades drop constraint if exists paper_trades_poi_lifecycle_state_check;
alter table public.paper_trades add constraint paper_trades_poi_lifecycle_state_check check (
  poi_lifecycle_state in (
    'untouched','grazed','partially_mitigated','midpoint_touched',
    'deep_unfilled','distal_touched','invalidated_close_through'
  )
);

create index if not exists paper_trades_focus_idx
  on public.paper_trades(symbol,focus_active,status,armed_at desc);

comment on column public.paper_trades.max_poi_penetration is
  'Maximum observed penetration from proximal edge toward distal edge. 0=proximal edge, 0.5=midpoint, 1=distal edge; may exceed 1 after traversal.';
comment on column public.paper_trades.focus_active is
  'Whether this historical research plan should compete for the live Focus card. Research tracking can continue when false.';
comment on column public.paper_trades.superseded_by_trade_key is
  'Newer same-symbol same-direction paper plan that supersedes this plan for Focus semantics. Does not delete or invalidate the older research observation.';

create table if not exists public.poi_depth_shadow (
  shadow_key text primary key,
  trade_key text not null references public.paper_trades(trade_key) on delete cascade,
  symbol text not null check (symbol in ('EURUSD','GBPUSD')),
  direction text not null check (direction in ('long','short')),
  depth_pct integer not null check (depth_pct between 0 and 100 and depth_pct % 5 = 0),
  eligible boolean not null,
  status text not null check (status in ('waiting','open','win','loss','timeout','ambiguous','ineligible')),
  entry_price numeric not null,
  stop_price numeric not null,
  target_price numeric not null,
  risk_distance numeric not null,
  risk_atr numeric not null,
  filled_at timestamptz,
  exit_at timestamptz,
  exit_price numeric,
  gross_r numeric,
  bars_to_entry integer,
  bars_held integer,
  resolution_timeframe text,
  ambiguous_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(trade_key, depth_pct)
);

create index if not exists poi_depth_shadow_status_idx
  on public.poi_depth_shadow(status,symbol,depth_pct,updated_at desc);
create index if not exists poi_depth_shadow_trade_idx
  on public.poi_depth_shadow(trade_key,depth_pct);

create table if not exists public.poi_penetration_events (
  event_key text primary key,
  trade_key text not null references public.paper_trades(trade_key) on delete cascade,
  symbol text not null check (symbol in ('EURUSD','GBPUSD')),
  direction text not null check (direction in ('long','short')),
  threshold_pct integer not null check (threshold_pct between 0 and 100),
  reached_at timestamptz not null,
  age_bars integer not null,
  observed_penetration numeric not null,
  before_midpoint boolean not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(trade_key, threshold_pct)
);

create index if not exists poi_penetration_events_trade_idx
  on public.poi_penetration_events(trade_key,reached_at);
create index if not exists poi_penetration_events_threshold_idx
  on public.poi_penetration_events(symbol,threshold_pct,reached_at desc);

alter table public.poi_depth_shadow enable row level security;
alter table public.poi_penetration_events enable row level security;

revoke all on public.poi_depth_shadow from anon, authenticated;
revoke all on public.poi_penetration_events from anon, authenticated;
grant select, insert, update, delete on public.poi_depth_shadow to service_role;
grant select, insert, update, delete on public.poi_penetration_events to service_role;

comment on table public.poi_depth_shadow is
  'Prospective research-only shadow entries across the frozen 0%-100% POI depth grid. No row can place a broker order or change the baseline midpoint paper plan.';
comment on table public.poi_penetration_events is
  'First observed threshold crossings for prospective POI reaction/lifecycle research.';
