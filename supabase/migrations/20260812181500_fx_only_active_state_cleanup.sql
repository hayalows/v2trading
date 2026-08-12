-- Production product scope is EURUSD + GBPUSD only.
-- Historical bars/research for retired markets remain archived, but retired markets
-- must not appear in active market state or unified V2.5 alert state.
delete from public.market_states where symbol not in ('EURUSD','GBPUSD');
delete from public.discord_alert_state
where state_key like '%XAUUSD%'
   or state_key like 'pulse:v25:%';
