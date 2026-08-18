create table if not exists public.v2_fast_execution_state (
  symbol text primary key,
  updated_at timestamptz not null default now(),
  status text not null default 'idle',
  source text,
  latest_bar timestamptz,
  active_trade_key text,
  active_trade_status text,
  last_action text,
  last_action_at timestamptz,
  provider_status text,
  details jsonb not null default '{}'::jsonb
);

create index if not exists v2_fast_execution_state_updated_idx
  on public.v2_fast_execution_state(updated_at desc);
