-- V2 v1.7 Shadow Arena
-- Immutable pre-outcome structural forecasts for prospective calibration.

create table if not exists public.shadow_model_registry (
  model_version text primary key,
  model_family text not null,
  status text not null check (status in ('baseline','historical_candidate','challenger','shadow','rejected','promoted')),
  probability_visible boolean not null default false,
  training_cutoff timestamptz,
  spec_hash text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.shadow_forecasts (
  forecast_key text primary key,
  symbol text not null check (symbol in ('EURUSD','GBPUSD')),
  campaign_key text not null,
  observed_at timestamptz not null,
  observed_bar_at timestamptz not null,
  direction text not null check (direction in ('long','short')),
  formation_stage smallint not null check (formation_stage in (3,4)),
  landmark_age_bars smallint not null check (landmark_age_bars in (0,2,4,8,12,16,24)),
  horizon_bars smallint not null default 16 check (horizon_bars in (8,16,32)),
  target_stage smallint not null default 5,
  regime text,
  baseline_probability double precision not null check (baseline_probability >= 0 and baseline_probability <= 1),
  predictions jsonb not null default '{}'::jsonb,
  feature_snapshot jsonb not null,
  model_spec_hash text not null,
  status text not null default 'pending' check (status in ('pending','resolved','censored')),
  outcome smallint check (outcome in (0,1)),
  outcome_at timestamptz,
  resolution_reason text,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (symbol,campaign_key,landmark_age_bars,horizon_bars)
);

create index if not exists shadow_forecasts_status_idx on public.shadow_forecasts(status, observed_at);
create index if not exists shadow_forecasts_symbol_idx on public.shadow_forecasts(symbol, observed_at desc);
create index if not exists shadow_forecasts_campaign_idx on public.shadow_forecasts(campaign_key);

alter table public.shadow_model_registry enable row level security;
alter table public.shadow_forecasts enable row level security;

grant select,insert,update,delete on table public.shadow_model_registry to service_role;
grant select,insert,update,delete on table public.shadow_forecasts to service_role;

insert into public.shadow_model_registry(model_version,model_family,status,probability_visible,training_cutoff,spec_hash,metadata)
values
  ('walkforward-base-v1','historical base rate','baseline',false,'2025-12-31T23:59:59Z','v17-base-primary-h16',jsonb_build_object('target','Stage 3/4 to same-direction Stage 5 within 16 M15 bars','p',0.1999597828272672,'source','frozen 2026 walk-forward comparator trained through 2025')),
  ('state-twin-v16','V2 structural ensemble','historical_candidate',false,'2025-12-31T23:59:59Z','v16-state-twin-frozen-gate',jsonb_build_object('historicalAuc',0.6882589530377745,'historicalBrier',0.1464929610215947,'livePolicy','ABSTAIN pending prospective calibration')),
  ('granite-ttm-r2-v17','IBM Granite Tiny Time Mixer R2','challenger',false,'2025-12-31T23:59:59Z','v17-ttm-r2-structural-challenger',jsonb_build_object('model','ibm-granite/granite-timeseries-ttm-r2','role','offline challenger; no product influence'))
on conflict (model_version) do update set
  metadata=excluded.metadata,
  spec_hash=excluded.spec_hash,
  updated_at=now();
