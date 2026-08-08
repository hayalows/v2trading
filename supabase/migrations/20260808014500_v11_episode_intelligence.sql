create table if not exists public.formation_episodes (
  episode_key text primary key,
  symbol text not null check (symbol in ('EURUSD','GBPUSD')),
  direction text not null check (direction in ('long','short')),
  status text not null default 'active' check (status in ('active','ended')),
  started_at timestamptz not null,
  ended_at timestamptz,
  end_reason text,
  last_seen_at timestamptz not null,
  max_stage smallint not null default 3 check (max_stage between 3 and 8),
  stage3_at timestamptz,
  stage4_at timestamptz,
  stage5_at timestamptz,
  stage6_at timestamptz,
  stage7_at timestamptz,
  stage8_at timestamptz,
  stage3_price numeric,
  stage5_price numeric,
  stage6_price numeric,
  stage3_atr numeric,
  stage5_atr numeric,
  stage6_atr numeric,
  anchor_context jsonb not null default '{}'::jsonb,
  source_meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists formation_episodes_symbol_started_idx on public.formation_episodes(symbol,started_at desc);
create index if not exists formation_episodes_status_idx on public.formation_episodes(status,symbol);

create table if not exists public.episode_outcomes (
  episode_key text not null references public.formation_episodes(episode_key) on delete cascade,
  anchor_stage smallint not null check (anchor_stage in (3,5,6)),
  anchor_at timestamptz not null,
  direction text not null check (direction in ('long','short')),
  anchor_price numeric not null,
  atr_at_anchor numeric,
  ret_15m_bps numeric, ret_30m_bps numeric, ret_1h_bps numeric, ret_2h_bps numeric, ret_4h_bps numeric,
  signed_ret_15m_bps numeric, signed_ret_30m_bps numeric, signed_ret_1h_bps numeric, signed_ret_2h_bps numeric, signed_ret_4h_bps numeric,
  mfe_1h_atr numeric, mae_1h_atr numeric, mfe_4h_atr numeric, mae_4h_atr numeric,
  complete_through_minutes integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (episode_key,anchor_stage)
);
create index if not exists episode_outcomes_stage_idx on public.episode_outcomes(anchor_stage,anchor_at desc);

alter table public.formation_episodes enable row level security;
alter table public.episode_outcomes enable row level security;
revoke all on public.formation_episodes from anon,authenticated;
revoke all on public.episode_outcomes from anon,authenticated;
grant all on public.formation_episodes to service_role;
grant all on public.episode_outcomes to service_role;

-- Schedule after the 5-minute market-state collector. This remains idempotent because episode keys are deterministic.
select cron.schedule(
  'v2-episode-engine-15m',
  '4,19,34,49 * * * *',
  $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/episode-engine');$$
);
