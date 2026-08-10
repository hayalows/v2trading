create table if not exists public.formation_campaigns (
  campaign_key text primary key,
  symbol text not null check (symbol in ('EURUSD','GBPUSD')),
  direction text not null check (direction in ('long','short')),
  status text not null default 'active' check (status in ('active','ended')),
  started_at timestamptz not null,
  ended_at timestamptz,
  end_reason text,
  last_seen_at timestamptz not null,
  max_stage smallint not null default 3 check (max_stage between 3 and 8),
  sweep_count integer not null default 0 check (sweep_count >= 0),
  first_sweep_time timestamptz,
  last_sweep_time timestamptz,
  stage5_at timestamptz,
  stage6_at timestamptz,
  stage7_at timestamptz,
  stage8_at timestamptz,
  anchor_context jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists formation_campaigns_symbol_started_idx on public.formation_campaigns(symbol, started_at desc);
create index if not exists formation_campaigns_status_idx on public.formation_campaigns(symbol, status, started_at desc);
create unique index if not exists formation_campaigns_one_active_per_symbol on public.formation_campaigns(symbol) where status='active';

alter table public.formation_campaigns enable row level security;
revoke all on public.formation_campaigns from anon, authenticated;
grant all on public.formation_campaigns to service_role;
drop policy if exists formation_campaigns_deny_anon on public.formation_campaigns;
create policy formation_campaigns_deny_anon on public.formation_campaigns for all to anon using (false) with check (false);
drop policy if exists formation_campaigns_deny_authenticated on public.formation_campaigns;
create policy formation_campaigns_deny_authenticated on public.formation_campaigns for all to authenticated using (false) with check (false);

create or replace function public.v2_campaign_context(p_as_of timestamptz, p_state jsonb)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'observedAt', p_as_of,
    'session', p_state->>'session',
    'trends', coalesce(p_state->'trends','{}'::jsonb),
    'formation', coalesce(p_state->'formation','{}'::jsonb),
    'structurePrice', p_state->'structurePrice',
    'dataHealth', coalesce(p_state->'dataHealth', p_state->'data_health', '{}'::jsonb)
  );
$$;

create or replace function public.v2_apply_campaign_state(
  p_symbol text,
  p_as_of timestamptz,
  p_stage integer,
  p_direction text,
  p_state jsonb
) returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_key text;
  v_dir text;
  v_stage5 timestamptz;
  v_stage6 timestamptz;
  v_stage7 timestamptz;
  v_stage8 timestamptz;
  v_sweep_text text;
  v_sweep timestamptz;
  v_first_sweep timestamptz;
  v_last_sweep timestamptz;
  v_sweep_count integer;
  v_anchor jsonb;
begin
  select campaign_key,direction,stage5_at,stage6_at,stage7_at,stage8_at,
         first_sweep_time,last_sweep_time,sweep_count,anchor_context
    into v_key,v_dir,v_stage5,v_stage6,v_stage7,v_stage8,
         v_first_sweep,v_last_sweep,v_sweep_count,v_anchor
  from public.formation_campaigns
  where symbol=p_symbol and status='active'
  order by started_at desc
  limit 1
  for update;

  v_sweep_text := p_state #>> '{formation,details,sweepTime}';
  begin
    v_sweep := nullif(v_sweep_text,'')::timestamptz;
  exception when others then
    v_sweep := null;
  end;

  if coalesce(p_stage,0) >= 3 and p_direction in ('long','short') then
    if v_key is not null and v_dir is distinct from p_direction then
      update public.formation_campaigns
         set status='ended', ended_at=p_as_of, end_reason='direction_flip', updated_at=now()
       where campaign_key=v_key;
      v_key := null;
    end if;

    if v_key is null then
      v_key := p_symbol || ':' || p_direction || ':' || to_char(p_as_of at time zone 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"');
      insert into public.formation_campaigns(
        campaign_key,symbol,direction,status,started_at,last_seen_at,max_stage,
        sweep_count,first_sweep_time,last_sweep_time,stage5_at,stage6_at,stage7_at,stage8_at,anchor_context
      ) values (
        v_key,p_symbol,p_direction,'active',p_as_of,p_as_of,greatest(3,least(8,p_stage)),
        case when v_sweep is null then 0 else 1 end,v_sweep,v_sweep,
        case when p_stage>=5 then p_as_of end,
        case when p_stage>=6 then p_as_of end,
        case when p_stage>=7 then p_as_of end,
        case when p_stage>=8 then p_as_of end,
        jsonb_build_object('stage3',public.v2_campaign_context(p_as_of,p_state))
        || case when p_stage>=5 then jsonb_build_object('stage5',public.v2_campaign_context(p_as_of,p_state)) else '{}'::jsonb end
        || case when p_stage>=6 then jsonb_build_object('stage6',public.v2_campaign_context(p_as_of,p_state)) else '{}'::jsonb end
      )
      on conflict (campaign_key) do nothing;
    else
      update public.formation_campaigns
         set last_seen_at=p_as_of,
             max_stage=greatest(max_stage,least(8,p_stage)),
             sweep_count=sweep_count + case when v_sweep is not null and last_sweep_time is distinct from v_sweep then 1 else 0 end,
             first_sweep_time=coalesce(first_sweep_time,v_sweep),
             last_sweep_time=case when v_sweep is not null and last_sweep_time is distinct from v_sweep then v_sweep else last_sweep_time end,
             stage5_at=case when p_stage>=5 then coalesce(stage5_at,p_as_of) else stage5_at end,
             stage6_at=case when p_stage>=6 then coalesce(stage6_at,p_as_of) else stage6_at end,
             stage7_at=case when p_stage>=7 then coalesce(stage7_at,p_as_of) else stage7_at end,
             stage8_at=case when p_stage>=8 then coalesce(stage8_at,p_as_of) else stage8_at end,
             anchor_context=anchor_context
               || case when p_stage>=5 and stage5_at is null then jsonb_build_object('stage5',public.v2_campaign_context(p_as_of,p_state)) else '{}'::jsonb end
               || case when p_stage>=6 and stage6_at is null then jsonb_build_object('stage6',public.v2_campaign_context(p_as_of,p_state)) else '{}'::jsonb end,
             updated_at=now()
       where campaign_key=v_key;
    end if;
  elsif v_key is not null then
    update public.formation_campaigns
       set status='ended', ended_at=p_as_of, end_reason='formation_reset', updated_at=now()
     where campaign_key=v_key;
  end if;
end;
$$;

revoke all on function public.v2_apply_campaign_state(text,timestamptz,integer,text,jsonb) from public, anon, authenticated;
grant execute on function public.v2_apply_campaign_state(text,timestamptz,integer,text,jsonb) to service_role;

create or replace function public.v2_campaign_history_trigger()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.v2_apply_campaign_state(NEW.symbol,NEW.as_of,NEW.formation_stage,NEW.formation_direction,NEW.state);
  return NEW;
end;
$$;

drop trigger if exists trg_v2_campaign_history on public.market_state_history;
create trigger trg_v2_campaign_history
after insert on public.market_state_history
for each row execute function public.v2_campaign_history_trigger();

-- Clean deterministic backfill from the untouched prospective history.
truncate table public.formation_campaigns;
do $$
declare r record;
begin
  for r in
    select symbol,as_of,formation_stage,formation_direction,state
    from public.market_state_history
    where symbol in ('EURUSD','GBPUSD')
    order by symbol,as_of
  loop
    perform public.v2_apply_campaign_state(r.symbol,r.as_of,r.formation_stage,r.formation_direction,r.state);
  end loop;
end $$;
