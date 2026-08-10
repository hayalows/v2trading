do $$
declare j record;
begin
  for j in select jobid from cron.job where jobname = 'v2-paper-trade-engine-5m' loop
    perform cron.unschedule(j.jobid);
  end loop;
  perform cron.schedule(
    'v2-paper-trade-engine-5m',
    '2-57/5 * * * *',
    $job$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/paper-trade-engine?run=1&symbol=EURUSD,GBPUSD');$job$
  );
end $$;
