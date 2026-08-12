-- Reduce constant Edge-runtime contention on the free-tier project.
-- XAU structure is M15-based, so a two-minute state refresh remains much
-- faster than the structural decision cadence. Discord runs on alternating
-- minutes and reads the latest saved state, avoiding both heavy jobs starting
-- together every minute.
do $$
declare
  xau_job bigint;
  discord_job bigint;
begin
  select jobid into xau_job from cron.job where jobname = 'v2-xau-state-1m' limit 1;
  if xau_job is not null then
    perform cron.alter_job(xau_job, schedule := '*/2 * * * *');
  end if;

  select jobid into discord_job from cron.job where jobname = 'v2-discord-v25-1m' limit 1;
  if discord_job is not null then
    perform cron.alter_job(discord_job, schedule := '1-59/2 * * * *');
  end if;
end $$;
