-- Run the v1.4 lifecycle evaluator two minutes after each five-minute market refresh.
select cron.unschedule(jobid) from cron.job where jobname = 'v2-paper-trade-engine-5m';
select cron.schedule(
  'v2-paper-trade-engine-5m',
  '2-57/5 * * * *',
  $$select net.http_get(url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/paper-trade-engine?run=1&symbol=EURUSD,GBPUSD');$$
);
