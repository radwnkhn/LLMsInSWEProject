-- Alibi data model: users, uploads, analyses, rep measurements, LLM attempts,
-- validation results and feedback responses, with row-level security and a private video bucket.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- tables

create table if not exists public.users (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null default '',
  is_admin boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.uploads (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  lift text not null check (lift in ('squat', 'deadlift', 'bench_press')),
  note text check (note is null or char_length(note) <= 300),
  video_path text not null,
  filename text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.analyses (
  id uuid primary key default gen_random_uuid(),
  upload_id uuid not null references public.uploads (id) on delete cascade,
  user_id uuid not null references public.users (id) on delete cascade,
  lift text not null check (lift in ('squat', 'deadlift', 'bench_press')),
  status text not null default 'queued' check (status in ('queued', 'processing', 'done', 'failed')),
  final_status text check (final_status in ('passed_first_try', 'passed_after_retry', 'fallback', 'unanalyzable')),
  rep_count integer,
  camera_angle text check (camera_angle in ('side', 'front', 'angled')),
  top_fault_id text,
  result jsonb,
  unanalyzable_reason text,
  frame_path text,
  error text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);
create index if not exists analyses_user_created on public.analyses (user_id, created_at desc);

create table if not exists public.rep_measurements (
  id bigint generated always as identity primary key,
  analysis_id uuid not null references public.analyses (id) on delete cascade,
  rep integer not null check (rep >= 1),
  start_frame integer not null,
  turn_frame integer not null,
  end_frame integer not null,
  start_time double precision not null,
  end_time double precision not null,
  metrics jsonb not null default '{}'::jsonb,
  worst_frames jsonb not null default '{}'::jsonb,
  depth_reached boolean,
  unique (analysis_id, rep)
);

create table if not exists public.llm_attempts (
  id uuid primary key default gen_random_uuid(),
  analysis_id uuid not null references public.analyses (id) on delete cascade,
  attempt_number integer not null check (attempt_number between 1 and 3),
  output_text text not null,
  input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  passed boolean not null default false,
  created_at timestamptz not null default now(),
  unique (analysis_id, attempt_number)
);

create table if not exists public.validation_results (
  id bigint generated always as identity primary key,
  attempt_id uuid not null references public.llm_attempts (id) on delete cascade,
  analysis_id uuid not null references public.analyses (id) on delete cascade,
  code text not null,
  message text not null
);
create index if not exists validation_results_code on public.validation_results (code);

create table if not exists public.feedback_responses (
  analysis_id uuid not null references public.analyses (id) on delete cascade,
  user_id uuid not null references public.users (id) on delete cascade,
  rating integer check (rating between 1 and 5),
  tried_cue text check (tried_cue in ('yes', 'no', 'not_yet')),
  updated_at timestamptz not null default now(),
  primary key (analysis_id, user_id)
);

-- A profile row for every Supabase Auth user.
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.users (id, email) values (new.id, coalesce(new.email, '')) on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------- row-level security

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select is_admin from public.users where id = auth.uid()), false)
$$;

alter table public.users enable row level security;
alter table public.uploads enable row level security;
alter table public.analyses enable row level security;
alter table public.rep_measurements enable row level security;
alter table public.llm_attempts enable row level security;
alter table public.validation_results enable row level security;
alter table public.feedback_responses enable row level security;

grant usage on schema public to authenticated;
grant select on public.users, public.uploads, public.analyses, public.rep_measurements,
  public.llm_attempts, public.validation_results, public.feedback_responses to authenticated;
grant insert on public.uploads, public.analyses, public.feedback_responses to authenticated;
grant update on public.feedback_responses to authenticated;
grant execute on function public.is_admin() to authenticated;

create policy users_read on public.users for select to authenticated
  using (id = auth.uid() or public.is_admin());

create policy uploads_read on public.uploads for select to authenticated
  using (user_id = auth.uid() or public.is_admin());
create policy uploads_insert on public.uploads for insert to authenticated
  with check (user_id = auth.uid());

create policy analyses_read on public.analyses for select to authenticated
  using (user_id = auth.uid() or public.is_admin());
create policy analyses_insert on public.analyses for insert to authenticated
  with check (user_id = auth.uid());

create policy rep_measurements_read on public.rep_measurements for select to authenticated
  using (public.is_admin() or exists (
    select 1 from public.analyses a where a.id = analysis_id and a.user_id = auth.uid()));

-- Raw LLM output and validator logs are for admins only.
create policy llm_attempts_read on public.llm_attempts for select to authenticated using (public.is_admin());
create policy validation_results_read on public.validation_results for select to authenticated using (public.is_admin());

create policy feedback_read on public.feedback_responses for select to authenticated
  using (user_id = auth.uid() or public.is_admin());
create policy feedback_insert on public.feedback_responses for insert to authenticated
  with check (user_id = auth.uid());
create policy feedback_update on public.feedback_responses for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ---------------------------------------------------------------- storage

-- Videos live under <user id>/..., annotated frames under frames/<user id>/... .
insert into storage.buckets (id, name, public) values ('videos', 'videos', false)
on conflict (id) do update set public = false;

create policy videos_owner_read on storage.objects for select to authenticated
  using (bucket_id = 'videos' and (
    (storage.foldername(name))[1] = auth.uid()::text
    or ((storage.foldername(name))[1] = 'frames' and (storage.foldername(name))[2] = auth.uid()::text)
    or public.is_admin()));
