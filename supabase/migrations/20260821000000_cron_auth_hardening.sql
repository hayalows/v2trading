-- Cron-auth hardening for V2 edge functions.
-- Creates a DB-private shared secret and rebuilds every scheduled HTTP cron job
-- so it sends the secret as the x-v2-cron-key header.
--
-- Deployment order matters:
--   1. Apply this migration FIRST (crons start sending the key; functions still accept keyless calls).
--   2. Then deploy the hardened edge functions (they start enforcing the key).
-- Reads used by the dashboard remain anonymous; only mutating paths enforce the key.

create table if not exists public.v2_runtime_secrets (
  name text primary key,
  secret text not null,
  rotated_at timestamptz not null default now()
);

alter table public.v2_runtime_secrets enable row level security;

revoke all on public.v2_runtime_secrets from anon, authenticated;
grant select on public.v2_runtime_secrets to service_role;

insert into public.v2_runtime_secrets (name, secret)
values ('cron', replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', ''))
on conflict (name) do nothing;

do $cron_auth$
declare
  sec text;
  j record;
begin
  select secret into sec from public.v2_runtime_secrets where name = 'cron';
  if sec is null then
    raise exception 'v2_runtime_secrets cron secret missing';
  end if;

  for j in
    select * from (values
      ('v2-paper-trade-engine-5m',      'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/paper-trade-engine?run=1&symbol=EURUSD,GBPUSD', null::int),
      ('v17-shadow-arena',              'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/shadow-arena?run=1',                            null::int),
      ('v2-paper-fast-execution-1m',    'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/paper-fast-execution?run=1',                    20000),
      ('v2-discord-quality-2m',         'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/discord-quality-pulse',                         55000),
      ('v2-discord-alerts-5m',          'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/discord-alerts?run=1',                          null::int),
      ('v2-discord-fx-pulse-2m',        'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/discord-pulse',                                 55000),
      ('v2-discord-fx-closures-5m',     'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/discord-trade-closures',                        55000),
      ('v2-eurusd-duka-raw-sync',       'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/dukascopy-raw-sync',                            60000),
      ('v2-eurusd-canonical-5m-verifier','https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/eurusd-canonical-5m-verifier',                 8000),
      ('v2-episode-engine-15m',         'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/episode-engine',                                null::int),
      ('v2-eurusd-htf-refresh-15m',     'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/market-lab?symbol=EURUSD&force=1',              12000)
    ) as t(jobname, url, timeout_ms)
  loop
    if exists (select 1 from cron.job where jobname = j.jobname) then
      perform cron.alter_job(
        (select jobid from cron.job where jobname = j.jobname limit 1),
        command := case
          when j.timeout_ms is null then
            format('select net.http_get(url := %L, headers := %L::jsonb)',
                   j.url, json_build_object('x-v2-cron-key', sec)::text)
          else
            format('select net.http_get(url := %L, headers := %L::jsonb, timeout_milliseconds := %s)',
                   j.url, json_build_object('x-v2-cron-key', sec)::text, j.timeout_ms)
        end
      );
    end if;
  end loop;
end
$cron_auth$;
