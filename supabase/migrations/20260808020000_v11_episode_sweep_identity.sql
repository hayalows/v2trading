alter table public.formation_episodes add column if not exists sweep_time timestamptz;
create index if not exists formation_episodes_symbol_sweep_idx on public.formation_episodes(symbol,sweep_time desc);
