begin;

create policy discord_alert_log_no_client_access
  on public.discord_alert_log for all to anon, authenticated
  using (false) with check (false);
create policy discord_alert_state_no_client_access
  on public.discord_alert_state for all to anon, authenticated
  using (false) with check (false);
create policy market_raw_bars_no_client_access
  on public.market_raw_bars for all to anon, authenticated
  using (false) with check (false);
create policy poi_depth_shadow_no_client_access
  on public.poi_depth_shadow for all to anon, authenticated
  using (false) with check (false);
create policy poi_penetration_events_no_client_access
  on public.poi_penetration_events for all to anon, authenticated
  using (false) with check (false);
create policy research_data_quarantine_no_client_access
  on public.research_data_quarantine for all to anon, authenticated
  using (false) with check (false);
create policy shadow_forecasts_no_client_access
  on public.shadow_forecasts for all to anon, authenticated
  using (false) with check (false);
create policy shadow_model_registry_no_client_access
  on public.shadow_model_registry for all to anon, authenticated
  using (false) with check (false);

commit;
