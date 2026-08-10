drop policy if exists paper_trades_private on public.paper_trades;
create policy paper_trades_private on public.paper_trades
for all to anon, authenticated
using (false)
with check (false);

drop policy if exists paper_trade_events_private on public.paper_trade_events;
create policy paper_trade_events_private on public.paper_trade_events
for all to anon, authenticated
using (false)
with check (false);
