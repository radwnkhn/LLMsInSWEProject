-- US-27: a record of every upload an admin removed. The removal itself reuses the US-21 upload deletion,
-- so this table must not reference the upload (it is deleted); it keeps only what explains the removal.
-- If either account is deleted later, the entry stays and the reference becomes null.
create table if not exists public.moderation_log (
  id uuid primary key default gen_random_uuid(),
  upload_id uuid not null,
  analysis_ids uuid[] not null default '{}',
  lift text not null check (lift in ('squat', 'deadlift', 'bench_press')),
  owner_id uuid references public.users (id) on delete set null,
  removed_by uuid references public.users (id) on delete set null,
  reason text not null check (reason in ('off_topic', 'inappropriate', 'other')),
  note text check (note is null or length(note) <= 200),
  removed_at timestamptz not null default now()
);
create index if not exists moderation_log_removed_at on public.moderation_log (removed_at desc);
create index if not exists moderation_log_analysis_ids on public.moderation_log using gin (analysis_ids);

alter table public.moderation_log enable row level security;
-- The API uses a server-side connection; signed-in admins may read the log directly too.
drop policy if exists moderation_log_admin_read on public.moderation_log;
create policy moderation_log_admin_read on public.moderation_log for select to authenticated using (public.is_admin());

-- Usage charts count sign-ups and uploads by creation time.
create index if not exists users_created_at on public.users (created_at);
create index if not exists uploads_created_at on public.uploads (created_at);
