create or replace function public.v2_market_state_data_health_guard()
returns trigger
language plpgsql
set search_path to 'public'
as $function$
declare
  dh jsonb := coalesce(new.data_health, '{}'::jsonb);
  lag_bars integer := coalesce(nullif(dh->>'structureLagBars','')::integer, 0);
  gap_count integer := coalesce(nullif(dh->>'gapCount96','')::integer, 0);
  structural_gap_count integer := gap_count;
  effective_gap_count integer := gap_count;
  dup_count integer := coalesce(nullif(dh->>'duplicateCount96','')::integer, 0);
  explicitly_usable text := dh->>'structureUsable';
  quantized text := dh->'resolution'->>'quantized';
  blocked boolean;
  reason text;
  merged_details jsonb;
  persisted_last timestamptz;
  incoming_last timestamptz;
  old_last timestamptz;
  expected_last timestamptz;
  persisted_lag integer;
begin
  if new.symbol='EURUSD'
     and now() >= timestamptz '2026-08-11 18:30:00+00'
     and coalesce(new.chart_source,'') <> 'EURUSD canonical structure v1' then
    if tg_op='UPDATE' and old.chart_source='EURUSD canonical structure v1' then
      old.d1_trend := new.d1_trend;
      old.h4_trend := new.h4_trend;
      old.h1_trend := new.h1_trend;
      old.d1_strength := new.d1_strength;
      old.h4_strength := new.h4_strength;
      old.h1_strength := new.h1_strength;
      old.regime := new.regime;
      old.market_session := new.market_session;
      old.prev_day_high := new.prev_day_high;
      old.prev_day_low := new.prev_day_low;
      merged_details := coalesce(old.details,'{}'::jsonb);
      if new.details->'trends'->'d1' is not null then merged_details := jsonb_set(merged_details,'{trends,d1}',new.details->'trends'->'d1',true); end if;
      if new.details->'trends'->'h4' is not null then merged_details := jsonb_set(merged_details,'{trends,h4}',new.details->'trends'->'h4',true); end if;
      if new.details->'trends'->'h1' is not null then merged_details := jsonb_set(merged_details,'{trends,h1}',new.details->'trends'->'h1',true); end if;
      if new.details->'diagnostics' is not null then merged_details := jsonb_set(merged_details,'{diagnostics}',new.details->'diagnostics',true); end if;
      merged_details := merged_details || jsonb_build_object('htfContextAt',coalesce(new.as_of,new.updated_at),'htfContextSource',new.chart_source);
      old.details := merged_details;
      old.data_health := coalesce(old.data_health,'{}'::jsonb) || jsonb_build_object('htfContextAt',coalesce(new.as_of,new.updated_at),'htfContextSource',new.chart_source);
      return old;
    end if;
    new.formation_stage := 0;
    new.formation_code := 'DATA_DEGRADED';
    new.formation_label := 'Structure withheld — deprecated EURUSD source blocked';
    new.formation_direction := null;
    new.formation_confidence := 0;
    new.poi_high := null;
    new.poi_low := null;
    new.distance_to_poi_atr := null;
    new.data_health := dh || jsonb_build_object('structureUsable',false,'blockedReason','Structure withheld — deprecated EURUSD source blocked','circuitBreaker',true,'deprecatedSourceBlocked',new.chart_source);
    return new;
  end if;

  if new.symbol='GBPUSD' then
    select count(*)::integer into structural_gap_count
    from (
      select ts, lag(ts) over(order by ts) as prev
      from (
        select distinct ts
        from public.market_bars
        where symbol='GBPUSD' and timeframe='15m' and coalesce(is_proxy,false)=false and source ilike 'Yahoo Finance public chart%'
        order by ts desc
        limit 33
      ) q
    ) x
    where prev is not null and ts-prev > interval '22 minutes 30 seconds' and ts-prev < interval '24 hours';
    structural_gap_count := coalesce(structural_gap_count, gap_count);
    effective_gap_count := structural_gap_count;
    dh := dh || jsonb_build_object('structuralGapCount32',structural_gap_count,'gapCount96MonitorOnly',gap_count);
    new.data_health := dh;
  end if;

  if new.symbol='GBPUSD' and tg_op='UPDATE' and lag_bars > 0 then
    begin
      incoming_last := nullif(dh->>'lastM15Bar','')::timestamptz;
      old_last := nullif(coalesce(old.data_health,'{}'::jsonb)->>'lastM15Bar','')::timestamptz;
    exception when others then
      incoming_last := null;
      old_last := null;
    end;
    select max(ts) into persisted_last from public.market_bars
    where symbol='GBPUSD' and timeframe='15m' and coalesce(is_proxy,false)=false and source ilike 'Yahoo Finance public chart%';
    if incoming_last is not null and old_last is not null and persisted_last is not null
       and persisted_last > incoming_last and old_last = persisted_last and coalesce(old.formation_code,'') <> 'DATA_DEGRADED' then
      expected_last := to_timestamp(floor(extract(epoch from now()) / 900) * 900 - 900);
      persisted_lag := greatest(0, round(extract(epoch from (expected_last - persisted_last)) / 900.0)::integer);
      new.chart_source := old.chart_source;
      new.m15_trend := old.m15_trend;
      new.m15_strength := old.m15_strength;
      new.formation_stage := old.formation_stage;
      new.formation_code := old.formation_code;
      new.formation_label := old.formation_label;
      new.formation_direction := old.formation_direction;
      new.formation_confidence := old.formation_confidence;
      new.atr15 := old.atr15;
      new.range_position := old.range_position;
      new.swing_high := old.swing_high;
      new.swing_low := old.swinging_low;
      new.poi_high := old.poi_high;
      new.poi_low := old.poi_low;
      new.distance_to_poi_atr := old.distance_to_poi_atr;
      new.research_summary := old.research_summary;
      merged_details := coalesce(new.details,'{}'::jsonb);
      if old.details->'trends'->'m15' is not null then merged_details := jsonb_set(merged_details,'{trends,m15}',old.details->'trends'->'m15',true); end if;
      if old.details->'formation' is not null then merged_details := jsonb_set(merged_details,'{formation}',old.details->'formation',true); end if;
      if old.details->'structure_reference_price' is not null then merged_details := jsonb_set(merged_details,'{structure_reference_price}',old.details->'structure_reference_price',true); end if;
      if old.details->'diagnostics' is not null then merged_details := jsonb_set(merged_details,'{diagnostics}',old.details->'diagnostics',true); end if;
      merged_details := merged_details || jsonb_build_object('providerRegressionGuard',true,'regressedProviderLastM15',incoming_last,'preservedValidatedLastM15',persisted_last);
      new.details := merged_details;
      dh := coalesce(old.data_health,'{}'::jsonb) || jsonb_build_object(
        'lastM15Bar',persisted_last,'expectedLastCompletedM15',expected_last,'structureLagBars',persisted_lag,
        'structureStatus',case when persisted_lag=0 then 'current completed candle' when persisted_lag=1 then 'one bar behind' else 'stale' end,
        'structureUsable',persisted_lag=0,'blockedReason',case when persisted_lag=0 then null else format('Structure withheld — feed %s bar(s) behind',persisted_lag) end,
        'circuitBreaker',true,'providerRegressionGuard',true,'regressedProviderLastM15',incoming_last,'preservedValidatedLastM15',persisted_last,
        'structuralGapCount32',structural_gap_count,'gapCount96MonitorOnly',gap_count
      );
      new.data_health := dh;
      lag_bars := persisted_lag;
      effective_gap_count := structural_gap_count;
      dup_count := coalesce(nullif(dh->>'duplicateCount96','')::integer, 0);
      explicitly_usable := dh->>'structureUsable';
      quantized := dh->'resolution'->>'quantized';
    end if;
  end if;

  blocked := new.formation_code = 'DATA_DEGRADED' or explicitly_usable = 'false' or quantized = 'true' or lag_bars > 0 or effective_gap_count > 0 or dup_count > 0;
  if blocked then
    reason := case
      when explicitly_usable = 'false' and coalesce(dh->>'blockedReason','') <> '' then dh->>'blockedReason'
      when quantized = 'true' then 'Structure withheld — quantized price feed'
      when lag_bars > 0 then format('Structure withheld — feed %s bar(s) behind', lag_bars)
      when effective_gap_count > 0 then format('Structure withheld — %s recent structural M15 gap(s)', effective_gap_count)
      when dup_count > 0 then format('Structure withheld — %s duplicate M15 bar(s)', dup_count)
      else 'Structure withheld — data quality gate'
    end;
    new.formation_stage := 0;
    new.formation_code := 'DATA_DEGRADED';
    new.formation_label := reason;
    new.formation_direction := null;
    new.formation_confidence := 0;
    new.poi_high := null;
    new.poi_low := null;
    new.distance_to_poi_atr := null;
    new.data_health := dh || jsonb_build_object('structureUsable',false,'blockedReason',reason,'circuitBreaker',true);
    new.details := coalesce(new.details,'{}'::jsonb) || jsonb_build_object('formation',jsonb_build_object('blocked',true,'reason',reason),'dataQualityCircuitBreaker',true);
  else
    new.data_health := dh || jsonb_build_object('structureUsable',true,'blockedReason',null,'circuitBreaker',true);
  end if;
  return new;
end;
$function$;
