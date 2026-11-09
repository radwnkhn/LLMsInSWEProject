-- US-19: keep job status stable while exposing the current analysis step to polling clients.
alter table public.analyses
  add column if not exists processing_stage text
  check (processing_stage in ('measuring', 'writing_feedback', 'checking'));
