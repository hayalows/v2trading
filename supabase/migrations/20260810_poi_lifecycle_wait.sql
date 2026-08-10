-- V2 v1.4: separate waiting time from structural invalidation.
-- An unfilled midpoint is no longer invalidated merely because 8 M15 bars elapsed.

alter table public.paper_trades
  alter column entry_expires_at drop not null;

alter table public.paper_trades
  add column if not exists lifecycle_phase text not null default 'fresh_wait',
  add column if not exists pending_age_bars integer not null default 0,
  add column if not exists first_zone_touch_at timestamptz,
  add column if not exists first_zone_touch_bar integer,
  add column if not exists pre_entry_max_favorable_r numeric,
  add column if not exists pre_entry_target_reached boolean not null default false,
  add column if not exists setup_condition text not null default 'intact',
  add column if not exists research_tail_bars integer not null default 192;

alter table public.paper_trades drop constraint if exists paper_trades_lifecycle_phase_check;
alter table public.paper_trades add constraint paper_trades_lifecycle_phase_check
  check (lifecycle_phase in ('fresh_wait','extended_wait','long_tail_wait','outside_studied_tail','filled','closed'));

alter table public.paper_trades drop constraint if exists paper_trades_setup_condition_check;
alter table public.paper_trades add constraint paper_trades_setup_condition_check
  check (setup_condition in ('intact','partially_mitigated','target_delivered_before_entry','partially_mitigated_after_target'));

comment on column public.paper_trades.lifecycle_phase is
  'Research waiting-time phase. Time alone does not mean structural invalidation.';
comment on column public.paper_trades.setup_condition is
  'Pre-entry POI condition. Shallow mitigation and target-delivered-before-entry are tracked as quality/context flags, not automatic cancellation.';
comment on column public.paper_trades.research_tail_bars is
  'Longest public-proxy time-to-fill horizon studied in v1.4. Plans may remain tracked beyond it but are outside validated waiting-time evidence.';
