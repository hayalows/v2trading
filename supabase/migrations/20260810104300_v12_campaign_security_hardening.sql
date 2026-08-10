alter function public.v2_campaign_context(timestamptz,jsonb) set search_path = public;
revoke all on function public.v2_campaign_context(timestamptz,jsonb) from public, anon, authenticated;
grant execute on function public.v2_campaign_context(timestamptz,jsonb) to service_role;

revoke all on function public.v2_campaign_history_trigger() from public, anon, authenticated;
grant execute on function public.v2_campaign_history_trigger() to service_role;
