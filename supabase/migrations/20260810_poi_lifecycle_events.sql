-- V2 v1.4 lifecycle event vocabulary.
alter table public.paper_trade_events drop constraint if exists paper_trade_events_event_type_check;
alter table public.paper_trade_events add constraint paper_trade_events_event_type_check check (
  event_type in (
    'armed','entry','win','loss','timeout','ambiguous','expired','invalid','update',
    'reactivated_v14','extended_wait','long_tail_wait','outside_studied_tail',
    'partially_mitigated','target_delivered_before_entry'
  )
);
