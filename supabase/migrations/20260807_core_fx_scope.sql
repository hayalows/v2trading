-- V2 Research Lab v0.6: core live scope is EURUSD + GBPUSD.
-- XAUUSD remains experimental and is not refreshed by the automatic five-minute scan.
-- US30 is paused.

update public.instruments
set active = (symbol in ('EURUSD','GBPUSD')),
    role = case
      when symbol in ('EURUSD','GBPUSD') then 'core_research'
      when symbol = 'XAUUSD' then 'experimental'
      else 'paused'
    end
where symbol in ('EURUSD','GBPUSD','XAUUSD','US30');

-- Production job id is environment-specific; use the named job after deployment:
-- select cron.alter_job(
--   (select jobid from cron.job where jobname='v2-market-lab-refresh-5m'),
--   command := $$select net.http_get(url := 'https://<project-ref>.supabase.co/functions/v1/market-lab?symbol=EURUSD,GBPUSD');$$
-- );
