do $$
declare j bigint;
begin
  select jobid into j from cron.job where jobname='v2-discord-quality-2m' limit 1;
  if j is not null then perform cron.unschedule(j); end if;
end $$;
select cron.schedule(
  'v2-discord-quality-2m',
  '1-59/2 * * * *',
  $job$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/discord-quality-pulse', timeout_milliseconds := 55000);$job$
);
