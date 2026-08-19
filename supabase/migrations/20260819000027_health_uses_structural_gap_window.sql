create or replace function public.v2_health_snapshot()
returns jsonb
language sql
stable security definer
set search_path to 'public','cron'
as $$
with key_jobs as (
  select j.jobid,j.jobname,j.schedule,j.active,
         r.status as last_run_status,r.start_time as last_run_start,r.end_time as last_run_end
  from cron.job j
  left join lateral (
    select d.status,d.start_time,d.end_time
    from cron.job_run_details d
    where d.jobid=j.jobid
    order by d.start_time desc
    limit 1
  ) r on true
  where j.jobname in (
    'v2-paper-trade-engine-5m','v2-paper-fast-execution-1m',
    'v2-discord-fx-pulse-2m','v2-discord-fx-closures-5m','v2-discord-quality-2m',
    'v2-eurusd-fast-canonical','v2-market-lab-refresh-5m','v2-paper-execution-audit-10m',
    'v2-fx-microstructure-10m','v34-market-intelligence','v35-trend-candle-engine-1m'
  )
), states as (
  select symbol,as_of,updated_at,formation_stage,formation_label,formation_direction,reference_price,
         data_health->>'lastM15Bar' as last_m15_bar,
         data_health->>'expectedLastCompletedM15' as expected_last_completed_m15,
         coalesce((data_health->>'gapCount96')::int,0) as gap_count_96,
         coalesce((data_health->>'structuralGapCount32')::int,(data_health->>'gapCount96')::int,0) as structural_gap_count,
         coalesce((data_health->>'duplicateCount96')::int,0) as duplicate_count_96,
         coalesce((data_health->>'structureLagBars')::int,0) as structure_lag_bars,
         data_health->>'structureStatus' as structure_status,
         data_health->>'blockedReason' as blocked_reason
  from public.market_states where symbol in ('EURUSD','GBPUSD')
), trades as (
  select count(*) filter (where status='open') as open_trades,
         count(*) filter (where status='armed' and focus_active=true) as active_armed,
         max(updated_at) as latest_trade_update,max(entry_at) as latest_entry_at,max(exit_at) as latest_exit_at
  from public.paper_trades
), events as (
  select max(created_at) as latest_event_created,max(event_at) as latest_event_at from public.paper_trade_events
), discord as (
  select (select max(updated_at) from public.discord_alert_state) as heartbeat_at,
         (select max(sent_at) from public.discord_alert_log) as last_alert_sent_at,
         (select event_type from public.discord_alert_log order by sent_at desc limit 1) as last_alert_type,
         (select symbol from public.discord_alert_log order by sent_at desc limit 1) as last_alert_symbol,
         (select discord_message_id from public.discord_alert_log order by sent_at desc limit 1) as last_message_id
), audit as (
  select max(updated_at) as latest_audit_at,
         count(*) filter (where entry_confirmed=true) as confirmed_entries,
         count(*) as audited_trades
  from public.paper_trade_execution_audit
), fast as (
  select coalesce(jsonb_agg(to_jsonb(f) order by symbol),'[]'::jsonb) as rows
  from public.v2_fast_execution_state f
)
select jsonb_build_object(
  'generatedAt',now(),
  'marketStates',coalesce((select jsonb_agg(to_jsonb(states) order by symbol) from states),'[]'::jsonb),
  'paperTrades',(select to_jsonb(trades) from trades),
  'paperEvents',(select to_jsonb(events) from events),
  'discord',(select to_jsonb(discord) from discord),
  'executionAudit',(select to_jsonb(audit) from audit),
  'fastExecution',(select rows from fast),
  'jobs',coalesce((select jsonb_agg(to_jsonb(key_jobs) order by jobname) from key_jobs),'[]'::jsonb)
);
$$;
