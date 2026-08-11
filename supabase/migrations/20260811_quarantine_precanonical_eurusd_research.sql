create table if not exists public.research_data_quarantine (
  source_table text not null,
  record_key text not null,
  symbol text,
  observed_at timestamptz,
  reason text not null,
  payload jsonb not null,
  quarantined_at timestamptz not null default now(),
  primary key (source_table,record_key)
);
alter table public.research_data_quarantine enable row level security;
grant select,insert,update,delete on public.research_data_quarantine to service_role;
revoke all on public.research_data_quarantine from anon,authenticated;

insert into public.research_data_quarantine(source_table,record_key,symbol,observed_at,reason,payload)
select 'market_state_history', symbol||':'||as_of::text, symbol, as_of,
       'Pre-canonical EURUSD observation used Yahoo quantized/stale-capable intraday structure', to_jsonb(h)
from public.market_state_history h
where symbol='EURUSD' and as_of < timestamptz '2026-08-11 18:30:00+00'
on conflict do nothing;

insert into public.research_data_quarantine(source_table,record_key,symbol,observed_at,reason,payload)
select 'formation_campaigns', campaign_key, symbol, started_at,
       'Campaign derived from pre-canonical Yahoo EURUSD intraday structure', to_jsonb(c)
from public.formation_campaigns c
where symbol='EURUSD' and started_at < timestamptz '2026-08-11 18:30:00+00'
on conflict do nothing;

insert into public.research_data_quarantine(source_table,record_key,symbol,observed_at,reason,payload)
select 'formation_episodes', episode_key, symbol, started_at,
       'Episode derived from pre-canonical Yahoo EURUSD intraday structure', to_jsonb(e)
from public.formation_episodes e
where symbol='EURUSD' and started_at < timestamptz '2026-08-11 18:30:00+00'
on conflict do nothing;

insert into public.research_data_quarantine(source_table,record_key,symbol,observed_at,reason,payload)
select 'episode_outcomes', o.episode_key||':'||o.anchor_stage::text||':'||o.anchor_at::text, 'EURUSD', o.anchor_at,
       'Outcome label anchored to a pre-canonical Yahoo EURUSD formation episode', to_jsonb(o)
from public.episode_outcomes o
join public.formation_episodes e using(episode_key)
where e.symbol='EURUSD' and e.started_at < timestamptz '2026-08-11 18:30:00+00'
on conflict do nothing;

insert into public.research_data_quarantine(source_table,record_key,symbol,observed_at,reason,payload)
select 'shadow_forecasts', forecast_key, symbol, observed_at,
       'Shadow forecast/features derived from pre-canonical Yahoo EURUSD intraday structure', to_jsonb(f)
from public.shadow_forecasts f
where symbol='EURUSD' and observed_at < timestamptz '2026-08-11 18:30:00+00'
on conflict do nothing;

-- After archival, remove pre-canonical EURUSD records from live evidence/model tables.
-- episode_outcomes are removed by the formation_episodes ON DELETE CASCADE after they were archived above.
delete from public.shadow_forecasts
where symbol='EURUSD' and observed_at < timestamptz '2026-08-11 18:30:00+00';

delete from public.formation_episodes
where symbol='EURUSD' and started_at < timestamptz '2026-08-11 18:30:00+00';

delete from public.formation_campaigns
where symbol='EURUSD' and started_at < timestamptz '2026-08-11 18:30:00+00';

delete from public.market_state_history
where symbol='EURUSD' and as_of < timestamptz '2026-08-11 18:30:00+00';
