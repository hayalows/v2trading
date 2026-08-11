-- V2.2 uses one human-facing Discord notifier. It runs every minute so delivery
-- follows the completed-data research engine without adding a second market feed.
do $$
declare j record;
begin
  for j in select jobid from cron.job where jobname in ('v2-discord-alerts-5m','v2-discord-pulse-1m') loop
    perform cron.unschedule(j.jobid);
  end loop;
end $$;

select cron.schedule(
  'v2-discord-pulse-1m',
  '* * * * *',
  $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/discord-pulse');$$
);
