create or replace function public.enforce_provider_cache_ttl()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  -- Anonymous gold is intentionally sampled hourly so the research lab remains
  -- inside its free monthly allowance. TradingView remains the visual market chart.
  if new.cache_key = 'goldprice-xau' then
    new.expires_at := greatest(new.expires_at, new.fetched_at + interval '60 minutes');
  -- The no-key FX reference can update more often, but five minutes is enough for
  -- the research UI and remains comfortably inside the free allowance.
  elsif new.cache_key = 'exchangerate-dev-usd' then
    new.expires_at := greatest(new.expires_at, new.fetched_at + interval '5 minutes');
  end if;
  return new;
end;
$$;

revoke execute on function public.enforce_provider_cache_ttl() from public, anon, authenticated;
grant execute on function public.enforce_provider_cache_ttl() to service_role;

drop trigger if exists provider_cache_ttl_guard on public.provider_cache;
create trigger provider_cache_ttl_guard
before insert or update on public.provider_cache
for each row execute function public.enforce_provider_cache_ttl();
