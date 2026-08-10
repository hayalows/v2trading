-- Run after the 5-minute market refresh. The function is idempotent per landmark.
do $$
begin
  if exists (select 1 from cron.job where jobname='v17-shadow-arena') then
    perform cron.unschedule((select jobid from cron.job where jobname='v17-shadow-arena' limit 1));
  end if;
end $$;

select cron.schedule(
  'v17-shadow-arena',
  '3-58/5 * * * *',
  $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/shadow-arena?run=1');$$
);
