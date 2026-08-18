create or replace function public.v2_protect_fast_bidask_execution()
returns trigger
language plpgsql
set search_path=public
as $$
declare
  fast_confirmed boolean := coalesce(old.context->'fast_execution'->>'confirmation','') = 'Dukascopy public BID/ASK tick';
begin
  if not fast_confirmed then
    return new;
  end if;

  if old.status in ('win','loss') and new.status in ('armed','open','expired') then
    return old;
  end if;

  if old.entry_at is not null then
    new.entry_at := old.entry_at;
  end if;

  if old.status='open' and new.status='open' and old.resolution_timeframe='bidask_tick_live' then
    new.resolution_timeframe := old.resolution_timeframe;
  end if;

  if old.context ? 'fast_execution' then
    new.context := coalesce(new.context,'{}'::jsonb)
      || jsonb_build_object('fast_execution',old.context->'fast_execution');
  end if;

  return new;
end;
$$;

drop trigger if exists trg_v2_protect_fast_bidask_execution on public.paper_trades;
create trigger trg_v2_protect_fast_bidask_execution
before update on public.paper_trades
for each row execute function public.v2_protect_fast_bidask_execution();
