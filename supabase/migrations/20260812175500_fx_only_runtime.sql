-- Reliability-first FX runtime: EURUSD + GBPUSD only.
-- Gold data/functions remain archived, but no Gold cron or unified V2.5 Discord job is active.

do $$
declare r record;
begin
  for r in select jobid from cron.job where jobname in (
    'v2-xau-state-1m',
    'v2-xau-history-reconcile-daily',
    'v2-discord-v25-1m',
    'v2-discord-fx-pulse-2m',
    'v2-discord-fx-closures-5m',
    'v2-eurusd-htf-refresh-15m'
  ) loop
    perform cron.unschedule(r.jobid);
  end loop;
end $$;

select cron.schedule(
  'v2-discord-fx-pulse-2m',
  '*/2 * * * *',
  $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/discord-pulse', timeout_milliseconds := 55000);$$
);

select cron.schedule(
  'v2-discord-fx-closures-5m',
  '1-56/5 * * * *',
  $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/discord-trade-closures', timeout_milliseconds := 55000);$$
);

-- Refresh D1/H4/H1 context before the canonical EURUSD M15 engine owns the final state row.
select cron.schedule(
  'v2-eurusd-htf-refresh-15m',
  '0,15,30,45 * * * *',
  $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/market-lab?symbol=EURUSD&force=1', timeout_milliseconds := 12000);$$
);

-- Model research is useful but is not allowed to compete with the core FX state machine.
do $$
declare j bigint;
begin
  select jobid into j from cron.job where jobname='v17-shadow-arena' limit 1;
  if j is not null then perform cron.alter_job(j, schedule := '3,18,33,48 * * * *'); end if;
  select jobid into j from cron.job where jobname='v24-exit-policy-lab' limit 1;
  if j is not null then perform cron.alter_job(j, active := false); end if;
end $$;
