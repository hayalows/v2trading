create table if not exists public.discord_alert_state (
  state_key text primary key,
  snapshot jsonb not null default '{}'::jsonb,
  last_sent_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists public.discord_alert_log (
  id bigint generated always as identity primary key,
  symbol text,
  event_type text not null,
  discord_message_id text,
  payload jsonb not null default '{}'::jsonb,
  sent_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists discord_alert_log_sent_idx
  on public.discord_alert_log(sent_at desc);
create index if not exists discord_alert_log_symbol_idx
  on public.discord_alert_log(symbol, sent_at desc);

alter table public.discord_alert_state enable row level security;
alter table public.discord_alert_log enable row level security;

revoke all on public.discord_alert_state from anon, authenticated;
revoke all on public.discord_alert_log from anon, authenticated;
grant select, insert, update, delete on public.discord_alert_state to service_role;
grant select, insert, update, delete on public.discord_alert_log to service_role;
grant usage, select on all sequences in schema public to service_role;

comment on table public.discord_alert_state is 'Private deduplication state for V2 Discord market alerts.';
comment on table public.discord_alert_log is 'Private audit log of V2 research-only Discord notifications.';

do $$
declare j record;
begin
  for j in select jobid from cron.job where jobname = 'v2-discord-alerts-5m' loop
    perform cron.unschedule(j.jobid);
  end loop;
  perform cron.schedule(
    'v2-discord-alerts-5m',
    '4-59/5 * * * *',
    $job$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/discord-alerts?run=1');$job$
  );
end $$;
