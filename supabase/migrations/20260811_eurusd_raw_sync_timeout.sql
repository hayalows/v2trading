do $job$
declare j bigint;
begin
  select jobid into j from cron.job where jobname='v2-eurusd-duka-raw-sync' limit 1;
  if j is not null then
    perform cron.alter_job(
      j,
      command := $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/dukascopy-raw-sync', timeout_milliseconds := 60000);$$
    );
  end if;
end
$job$;
