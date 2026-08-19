create table if not exists public.v2_live_feed_quotes_current (
  symbol text not null check (symbol in ('EURUSD','GBPUSD')),
  provider text not null,
  observed_at timestamptz not null,
  received_at timestamptz not null default now(),
  bid double precision not null,
  ask double precision not null,
  spread_pips double precision not null,
  quote_id text,
  status text not null default 'live',
  meta jsonb not null default '{}'::jsonb,
  primary key (symbol, provider),
  check (bid > 0 and ask >= bid),
  check (spread_pips >= 0 and spread_pips <= 50)
);

create table if not exists public.v2_live_feed_provider_state (
  provider text not null,
  symbol text not null check (symbol in ('EURUSD','GBPUSD')),
  status text not null default 'standby',
  last_tick_at timestamptz,
  last_received_at timestamptz,
  last_error text,
  connection_meta jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (provider, symbol)
);

create table if not exists public.v2_live_feed_crossings (
  id bigint generated always as identity primary key,
  event_key text not null unique,
  provider text not null,
  symbol text not null check (symbol in ('EURUSD','GBPUSD')),
  trade_key text,
  observed_at timestamptz not null,
  received_at timestamptz not null default now(),
  bid double precision not null,
  ask double precision not null,
  action text not null,
  applied boolean not null default false,
  details jsonb not null default '{}'::jsonb
);
create index if not exists v2_live_feed_crossings_trade_idx on public.v2_live_feed_crossings(trade_key, observed_at desc);
create index if not exists v2_live_feed_crossings_symbol_idx on public.v2_live_feed_crossings(symbol, observed_at desc);

create table if not exists public.v2_live_feed_ingest_keys (
  token_hash text primary key,
  label text not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  last_used_at timestamptz
);

alter table public.v2_live_feed_quotes_current enable row level security;
alter table public.v2_live_feed_provider_state enable row level security;
alter table public.v2_live_feed_crossings enable row level security;
alter table public.v2_live_feed_ingest_keys enable row level security;
revoke all on public.v2_live_feed_quotes_current from anon, authenticated;
revoke all on public.v2_live_feed_provider_state from anon, authenticated;
revoke all on public.v2_live_feed_crossings from anon, authenticated;
revoke all on public.v2_live_feed_ingest_keys from anon, authenticated;
grant all on public.v2_live_feed_quotes_current to service_role;
grant all on public.v2_live_feed_provider_state to service_role;
grant all on public.v2_live_feed_crossings to service_role;
grant all on public.v2_live_feed_ingest_keys to service_role;
grant usage, select on sequence public.v2_live_feed_crossings_id_seq to service_role;

create or replace function public.v2_apply_live_feed_quote(p_provider text,p_symbol text,p_observed_at timestamptz,p_bid double precision,p_ask double precision,p_quote_id text default null,p_meta jsonb default '{}'::jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare v_spread double precision; v_age_ms double precision;
begin
  if p_symbol not in ('EURUSD','GBPUSD') then raise exception 'unsupported symbol'; end if;
  if p_provider is null or length(trim(p_provider))<2 then raise exception 'provider required'; end if;
  if p_bid is null or p_ask is null or p_bid<=0 or p_ask<p_bid then raise exception 'invalid bid/ask'; end if;
  v_spread := (p_ask-p_bid)/0.0001;
  if v_spread<0 or v_spread>50 then raise exception 'spread out of bounds'; end if;
  v_age_ms := extract(epoch from (now()-p_observed_at))*1000.0;
  if v_age_ms>120000 or v_age_ms< -10000 then raise exception 'quote timestamp out of bounds'; end if;
  insert into public.v2_live_feed_quotes_current(symbol,provider,observed_at,received_at,bid,ask,spread_pips,quote_id,status,meta)
  values(p_symbol,trim(p_provider),p_observed_at,now(),p_bid,p_ask,v_spread,p_quote_id,'live',coalesce(p_meta,'{}'::jsonb))
  on conflict(symbol,provider) do update set observed_at=excluded.observed_at,received_at=excluded.received_at,bid=excluded.bid,ask=excluded.ask,spread_pips=excluded.spread_pips,quote_id=excluded.quote_id,status='live',meta=excluded.meta
  where excluded.observed_at>=v2_live_feed_quotes_current.observed_at;
  insert into public.v2_live_feed_provider_state(provider,symbol,status,last_tick_at,last_received_at,last_error,connection_meta,updated_at)
  values(trim(p_provider),p_symbol,'live',p_observed_at,now(),null,coalesce(p_meta,'{}'::jsonb),now())
  on conflict(provider,symbol) do update set status='live',last_tick_at=excluded.last_tick_at,last_received_at=excluded.last_received_at,last_error=null,connection_meta=excluded.connection_meta,updated_at=now();
  return jsonb_build_object('ok',true,'symbol',p_symbol,'provider',trim(p_provider),'observedAt',p_observed_at,'spreadPips',v_spread);
end $$;

create or replace function public.v2_canonical_live_quote(p_symbol text)
returns jsonb language sql security definer set search_path=public as $$
with latest as (
  select provider,symbol,observed_at,received_at,bid,ask,spread_pips,quote_id,meta,extract(epoch from (now()-observed_at))*1000.0 as age_ms
  from public.v2_live_feed_quotes_current where symbol=p_symbol and observed_at>=now()-interval '30 seconds'
), stats as (
  select count(*)::int provider_count,percentile_cont(0.5) within group(order by bid) median_bid,percentile_cont(0.5) within group(order by ask) median_ask,max(observed_at) newest_at,max(bid)-min(bid) bid_range,max(ask)-min(ask) ask_range,
  jsonb_agg(jsonb_build_object('provider',provider,'bid',bid,'ask',ask,'spreadPips',spread_pips,'observedAt',observed_at,'ageMs',greatest(0,age_ms),'quoteId',quote_id) order by provider) providers from latest
)
select jsonb_build_object('symbol',p_symbol,
  'status',case when provider_count=0 then 'unavailable' when extract(epoch from(now()-newest_at))*1000.0<=5000 then 'live' when extract(epoch from(now()-newest_at))*1000.0<=15000 then 'delayed' else 'stale' end,
  'mode',case when provider_count>=2 and greatest(coalesce(bid_range,0),coalesce(ask_range,0))/0.0001<=2 then 'consensus' when provider_count>=2 then 'provider_conflict' when provider_count=1 then 'single_source' else 'none' end,
  'providerCount',provider_count,'bid',median_bid,'ask',median_ask,'mid',case when median_bid is null or median_ask is null then null else (median_bid+median_ask)/2 end,
  'spreadPips',case when median_bid is null or median_ask is null then null else (median_ask-median_bid)/0.0001 end,
  'dispersionPips',greatest(coalesce(bid_range,0),coalesce(ask_range,0))/0.0001,'observedAt',newest_at,
  'ageMs',case when newest_at is null then null else greatest(0,extract(epoch from(now()-newest_at))*1000.0) end,'providers',coalesce(providers,'[]'::jsonb)) from stats;
$$;

create or replace function public.v2_live_feed_snapshot() returns jsonb language sql security definer set search_path=public as $$
select jsonb_build_object('generatedAt',now(),'quotes',jsonb_build_array(public.v2_canonical_live_quote('EURUSD'),public.v2_canonical_live_quote('GBPUSD')),
'providers',coalesce((select jsonb_agg(jsonb_build_object('provider',provider,'symbol',symbol,'status',status,'lastTickAt',last_tick_at,'lastReceivedAt',last_received_at,'updatedAt',updated_at,'lastError',last_error,'meta',connection_meta) order by provider,symbol) from public.v2_live_feed_provider_state),'[]'::jsonb),
'ingestConfigured',exists(select 1 from public.v2_live_feed_ingest_keys where active=true));
$$;

create or replace function public.v2_process_stream_quote(p_provider text,p_symbol text,p_observed_at timestamptz,p_bid double precision,p_ask double precision,p_quote_id text default null,p_meta jsonb default '{}'::jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare t public.paper_trades%rowtype; v_action text:='quote_only'; v_applied boolean:=false; v_event_key text; v_now timestamptz:=now(); v_eps double precision:=1e-9; v_entry_hit boolean:=false; v_stop_hit boolean:=false; v_target_hit boolean:=false; v_context jsonb;
begin
  perform public.v2_apply_live_feed_quote(p_provider,p_symbol,p_observed_at,p_bid,p_ask,p_quote_id,p_meta);
  select * into t from public.paper_trades where symbol=p_symbol and focus_active=true and status in ('armed','open') order by armed_at asc limit 1 for update;
  if not found then return jsonb_build_object('ok',true,'action','quote_only','applied',false,'symbol',p_symbol); end if;
  if p_observed_at<coalesce(t.armed_at,v_now)-interval '1 second' or p_observed_at>v_now+interval '10 seconds' then return jsonb_build_object('ok',true,'action','ignored_timestamp','applied',false,'tradeKey',t.trade_key); end if;
  if t.status='armed' then
    v_entry_hit:=case when t.direction='long' then p_ask<=t.entry_price+v_eps else p_bid>=t.entry_price-v_eps end;
    if not v_entry_hit then return jsonb_build_object('ok',true,'action','waiting','applied',false,'tradeKey',t.trade_key); end if;
    v_stop_hit:=case when t.direction='long' then p_bid<=t.stop_price+v_eps else p_ask>=t.stop_price-v_eps end;
    v_target_hit:=case when t.direction='long' then p_bid>=t.target_price-v_eps else p_ask<=t.target_price+v_eps end;
    if v_stop_hit or v_target_hit then v_action:='ambiguous_same_tick';
    else
      v_context:=coalesce(t.context,'{}'::jsonb)||jsonb_build_object('stream_execution',jsonb_build_object('provider',p_provider,'quoteId',p_quote_id,'observedAt',p_observed_at,'bid',p_bid,'ask',p_ask,'brokerSpecific',false,'structureRulesChanged',false,'confirmation','streamed public BID/ASK'));
      update public.paper_trades set status='open',entry_at=p_observed_at,resolution_timeframe='live_bidask_stream',lifecycle_phase='filled',context=v_context,updated_at=v_now where trade_key=t.trade_key and status='armed';
      get diagnostics v_applied=row_count; v_action:=case when v_applied then 'stream_entry' else 'race_skipped' end;
      if v_applied then insert into public.paper_trade_events(trade_key,event_at,event_type,price,payload) values(t.trade_key,p_observed_at,'stream_entry',t.entry_price,jsonb_build_object('provider',p_provider,'bid',p_bid,'ask',p_ask,'quoteId',p_quote_id,'resolution','live_bidask_stream')) on conflict(trade_key,event_type) do nothing; end if;
    end if;
  elsif t.status='open' then
    v_stop_hit:=case when t.direction='long' then p_bid<=t.stop_price+v_eps else p_ask>=t.stop_price-v_eps end;
    v_target_hit:=case when t.direction='long' then p_bid>=t.target_price-v_eps else p_ask<=t.target_price+v_eps end;
    if v_stop_hit and v_target_hit then v_action:='ambiguous_same_tick';
    elsif v_stop_hit or v_target_hit then
      v_action:=case when v_target_hit then 'stream_win' else 'stream_loss' end;
      v_context:=coalesce(t.context,'{}'::jsonb)||jsonb_build_object('stream_execution',jsonb_build_object('provider',p_provider,'quoteId',p_quote_id,'observedAt',p_observed_at,'bid',p_bid,'ask',p_ask,'brokerSpecific',false,'structureRulesChanged',false,'confirmation','streamed public BID/ASK','outcome',case when v_target_hit then 'win' else 'loss' end));
      update public.paper_trades set status=case when v_target_hit then 'win' else 'loss' end,lifecycle_phase='closed',focus_active=false,exit_at=p_observed_at,exit_price=case when v_target_hit then t.target_price else t.stop_price end,gross_r=case when v_target_hit then 2.5 else -1 end,resolution_timeframe='live_bidask_stream',context=v_context,updated_at=v_now where trade_key=t.trade_key and status='open';
      get diagnostics v_applied=row_count; if not v_applied then v_action:='race_skipped'; end if;
      if v_applied then insert into public.paper_trade_events(trade_key,event_at,event_type,price,payload) values(t.trade_key,p_observed_at,v_action,case when v_target_hit then t.target_price else t.stop_price end,jsonb_build_object('provider',p_provider,'bid',p_bid,'ask',p_ask,'quoteId',p_quote_id,'resolution','live_bidask_stream','grossR',case when v_target_hit then 2.5 else -1 end)) on conflict(trade_key,event_type) do nothing; end if;
    else v_action:='tracking'; end if;
  end if;
  v_event_key:=encode(digest(coalesce(p_provider,'')||'|'||coalesce(t.trade_key,'')||'|'||v_action||'|'||p_observed_at::text||'|'||p_bid::text||'|'||p_ask::text,'sha256'),'hex');
  insert into public.v2_live_feed_crossings(event_key,provider,symbol,trade_key,observed_at,bid,ask,action,applied,details) values(v_event_key,p_provider,p_symbol,t.trade_key,p_observed_at,p_bid,p_ask,v_action,v_applied,jsonb_build_object('quoteId',p_quote_id,'meta',coalesce(p_meta,'{}'::jsonb))) on conflict(event_key) do nothing;
  return jsonb_build_object('ok',true,'action',v_action,'applied',v_applied,'tradeKey',t.trade_key,'symbol',p_symbol,'statusBefore',t.status);
end $$;

revoke all on function public.v2_apply_live_feed_quote(text,text,timestamptz,double precision,double precision,text,jsonb) from public,anon,authenticated;
revoke all on function public.v2_process_stream_quote(text,text,timestamptz,double precision,double precision,text,jsonb) from public,anon,authenticated;
revoke all on function public.v2_live_feed_snapshot() from public,anon,authenticated;
revoke all on function public.v2_canonical_live_quote(text) from public,anon,authenticated;
grant execute on function public.v2_apply_live_feed_quote(text,text,timestamptz,double precision,double precision,text,jsonb) to service_role;
grant execute on function public.v2_process_stream_quote(text,text,timestamptz,double precision,double precision,text,jsonb) to service_role;
grant execute on function public.v2_live_feed_snapshot() to service_role;
grant execute on function public.v2_canonical_live_quote(text) to service_role;
