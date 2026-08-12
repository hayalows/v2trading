-- The EURUSD feed guard must keep canonical M15/POI geometry authoritative,
-- while still allowing the general FX engine to refresh D1/H4/H1 context.
create or replace function public.v2_market_state_data_health_guard()
returns trigger
language plpgsql
set search_path to 'public'
as $function$
declare
  dh jsonb := coalesce(new.data_health, '{}'::jsonb);
  lag_bars integer := coalesce(nullif(dh->>'structureLagBars','')::integer, 0);
  gap_count integer := coalesce(nullif(dh->>'gapCount96','')::integer, 0);
  dup_count integer := coalesce(nullif(dh->>'duplicateCount96','')::integer, 0);
  explicitly_usable text := dh->>'structureUsable';
  quantized text := dh->'resolution'->>'quantized';
  blocked boolean;
  reason text;
  merged_details jsonb;
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
      if new.details->'trends'->'d1' is not null then
        merged_details := jsonb_set(merged_details,'{trends,d1}',new.details->'trends'->'d1',true);
      end if;
      if new.details->'trends'->'h4' is not null then
        merged_details := jsonb_set(merged_details,'{trends,h4}',new.details->'trends'->'h4',true);
      end if;
      if new.details->'trends'->'h1' is not null then
        merged_details := jsonb_set(merged_details,'{trends,h1}',new.details->'trends'->'h1',true);
      end if;
      if new.details->'diagnostics' is not null then
        merged_details := jsonb_set(merged_details,'{diagnostics}',new.details->'diagnostics',true);
      end if;
      merged_details := merged_details || jsonb_build_object(
        'htfContextAt',coalesce(new.as_of,new.updated_at),
        'htfContextSource',new.chart_source
      );
      old.details := merged_details;
      old.data_health := coalesce(old.data_health,'{}'::jsonb) || jsonb_build_object(
        'htfContextAt',coalesce(new.as_of,new.updated_at),
        'htfContextSource',new.chart_source
      );
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
    new.data_health := dh || jsonb_build_object(
      'structureUsable',false,
      'blockedReason','Structure withheld — deprecated EURUSD source blocked',
      'circuitBreaker',true,
      'deprecatedSourceBlocked',new.chart_source
    );
    return new;
  end if;

  blocked := new.formation_code = 'DATA_DEGRADED'
    or explicitly_usable = 'false'
    or quantized = 'true'
    or lag_bars > 0
    or gap_count > 0
    or dup_count > 0;

  if blocked then
    reason := case
      when explicitly_usable = 'false' and coalesce(dh->>'blockedReason','') <> '' then dh->>'blockedReason'
      when quantized = 'true' then 'Structure withheld — quantized price feed'
      when lag_bars > 0 then format('Structure withheld — feed %s bar(s) behind', lag_bars)
      when gap_count > 0 then format('Structure withheld — %s recent M15 gap(s)', gap_count)
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
  end if;
  return new;
end;
$function$;
