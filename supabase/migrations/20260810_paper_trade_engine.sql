create table if not exists public.paper_trades (
  trade_key text primary key,
  symbol text not null check (symbol in ('EURUSD','GBPUSD')),
  campaign_key text,
  episode_key text,
  direction text not null check (direction in ('long','short')),
  status text not null check (status in ('armed','open','win','loss','timeout','ambiguous','expired','invalid')),
  armed_at timestamptz not null,
  sweep_time timestamptz not null,
  bos_time timestamptz not null,
  poi_time timestamptz,
  entry_expires_at timestamptz not null,
  poi_low numeric not null,
  poi_high numeric not null,
  entry_price numeric not null,
  stop_price numeric not null,
  target_price numeric not null,
  sweep_extreme numeric not null,
  atr_at_plan numeric not null,
  risk_distance numeric not null,
  risk_atr numeric not null,
  reward_r numeric not null default 2.5,
  entry_at timestamptz,
  exit_at timestamptz,
  exit_price numeric,
  gross_r numeric,
  bars_to_entry integer,
  bars_held integer,
  mfe_r numeric,
  mae_r numeric,
  resolution_timeframe text,
  ambiguous_reason text,
  context jsonb not null default '{}'::jsonb,
  source_note text not null default 'Public completed-candle research paper trade; not broker execution.',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists paper_trades_symbol_status_idx on public.paper_trades(symbol,status,armed_at desc);
create index if not exists paper_trades_bos_idx on public.paper_trades(symbol,bos_time desc);

create table if not exists public.paper_trade_events (
  id bigint generated always as identity primary key,
  trade_key text not null references public.paper_trades(trade_key) on delete cascade,
  event_at timestamptz not null,
  event_type text not null check (event_type in ('armed','entry','win','loss','timeout','ambiguous','expired','invalid','update')),
  price numeric,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists paper_trade_events_trade_idx on public.paper_trade_events(trade_key,event_at);

alter table public.paper_trades enable row level security;
alter table public.paper_trade_events enable row level security;

revoke all on public.paper_trades from anon, authenticated;
revoke all on public.paper_trade_events from anon, authenticated;
grant select, insert, update, delete on public.paper_trades to service_role;
grant select, insert, update, delete on public.paper_trade_events to service_role;
grant usage, select on all sequences in schema public to service_role;

comment on table public.paper_trades is 'Automatic V2 research paper trades. These are simulated bar-based research records, never broker fills.';
comment on table public.paper_trade_events is 'Event log for automatic V2 research paper trades.';
