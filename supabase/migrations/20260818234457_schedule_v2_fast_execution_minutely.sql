select cron.schedule(
  'v2-paper-fast-execution-1m',
  '* * * * *',
  $$select net.http_get(
    url := 'https://uykjgyqoptsvvkaifphm.supabase.co/functions/v1/paper-fast-execution?run=1',
    timeout_milliseconds := 20000
  );$$
);
