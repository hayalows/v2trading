-- V2 v1.8 Model Council frozen decisions.
-- Research-only: no probability visibility, Focus influence, paper-trade influence or execution claim.

insert into public.shadow_model_registry(
  model_version,model_family,status,probability_visible,training_cutoff,spec_hash,metadata
)
values
  (
    'state-twin-student-v18',
    'StateTwin compact logistic student',
    'shadow',
    false,
    '2025-12-31T23:59:59Z',
    'v18-state-twin-student-age0-frozen',
    jsonb_build_object(
      'decision','PROMOTE_STATE_TWIN_STUDENT_TO_SHADOW',
      'eligibleLandmarkAgeBars',jsonb_build_array(0),
      'completedCampaigns',8526,
      'auc',0.6574112337144489,
      'brier',0.1693802483725054,
      'baseBrier',0.17897405850101145,
      'brierImprovement',0.009593810128506047,
      'ece10',0.019762155360135265,
      'teacherAuc',0.664649606797921,
      'teacherBrier',0.16825063931641385,
      'teacherStudentCorrelation',0.9200072,
      'runId',31445594246,
      'artifactSha256','2ef94a7d5d28fbca8523c6f40c359d349cd53cc591a7a1f5d2d6095ec0361d62',
      'livePolicy','hidden age-0 prospective shadow scoring only'
    )
  ),
  (
    'model-council-v18',
    'StateTwin + Granite TTM convex council',
    'rejected',
    false,
    '2025-12-31T23:59:59Z',
    'v18-council-incremental-frozen-gate',
    jsonb_build_object(
      'decision','REJECT_COUNCIL_INCREMENTAL',
      'completedCampaigns',8526,
      'auc',0.6711703261928675,
      'brier',0.1676094884344941,
      'stateTwinBrier',0.16825063931641385,
      'ttmBrier',0.17075300210110453,
      'stateMinusCouncilBrier',0.0006411508819197825,
      'bootstrapLow95',-0.0002207100927050719,
      'bootstrapHigh95',0.0015163138908020192,
      'positiveOrEqualYears',2,
      'requiredYears',3,
      'reason','Pooled point estimate improved, but paired bootstrap crossed zero and year-level robustness gate failed.',
      'runId',31445594246,
      'artifactSha256','2ef94a7d5d28fbca8523c6f40c359d349cd53cc591a7a1f5d2d6095ec0361d62',
      'livePolicy','no Council probability; retain independent shadow observers'
    )
  )
on conflict (model_version) do update set
  model_family=excluded.model_family,
  status=excluded.status,
  probability_visible=excluded.probability_visible,
  training_cutoff=excluded.training_cutoff,
  spec_hash=excluded.spec_hash,
  metadata=excluded.metadata,
  updated_at=now();

update public.shadow_model_registry
set metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
  'eligibleLandmarkAgeBars',jsonb_build_array(0),
  'livePolicy','hidden age-0 prospective shadow scoring only; later campaign ages require separate validation'
), updated_at=now()
where model_version='granite-ttm-r2-v17';
