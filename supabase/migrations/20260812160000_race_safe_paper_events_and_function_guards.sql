-- Keep the research engine's event and shadow writes idempotent when a cron
-- invocation overlaps a retry. The existing live rows were checked before
-- adding this invariant; no duplicate (trade_key, event_type) rows exist.
begin;

create unique index if not exists paper_trade_events_trade_key_event_type_key
  on public.paper_trade_events (trade_key, event_type);

-- Trigger functions must resolve their intended application objects through an
-- explicit path. This removes the mutable-search-path advisor findings without
-- changing their trigger semantics.
alter function public.block_deprecated_eurusd_yahoo_m15() set search_path = public;
alter function public.v2_market_state_data_health_guard() set search_path = public;
alter function public.v2_suppress_unhealthy_state_history() set search_path = public;
alter function public.v2_eurusd_paper_arm_source_guard() set search_path = public;
alter function public.v2_guard_blocked_paper_events() set search_path = public;
alter function public.v2_guard_blocked_depth_shadow() set search_path = public;
alter function public.v2_censor_legacy_eurusd_5m_paper_resolution() set search_path = public;

-- The watchdog is invoked by the database cron job, not by a browser. Remove
-- its unnecessary public RPC surface while retaining service_role execution.
alter function public.v2_eurusd_feed_watchdog() set search_path = public;
revoke all on function public.v2_eurusd_feed_watchdog() from public, anon, authenticated;
grant execute on function public.v2_eurusd_feed_watchdog() to service_role;

commit;
