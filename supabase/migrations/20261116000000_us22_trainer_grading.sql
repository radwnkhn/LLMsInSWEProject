-- US-22: trainer accounts and blind grading. A trainer gets a sample of analyses, records their own top fault
-- for each video (trainer_fault_id; null with answered_at set means "No major issue"), and only then sees our
-- feedback and grades it. Deleting an upload, analysis or the trainer deletes their assignments.
alter table public.users add column if not exists is_trainer boolean not null default false;

create table if not exists public.grading_assignments (
  id uuid primary key default gen_random_uuid(),
  analysis_id uuid not null references public.analyses (id) on delete cascade,
  trainer_id uuid not null references public.users (id) on delete cascade,
  assigned_by uuid references public.users (id) on delete set null,
  assigned_at timestamptz not null default now(),
  trainer_fault_id text check (trainer_fault_id is null or trainer_fault_id ~ '^[a-z][a-z0-9_]{2,39}$'),
  answered_at timestamptz,
  verdict text check (verdict in ('correct', 'partly_correct', 'wrong')),
  graded_at timestamptz,
  unique (analysis_id, trainer_id),
  check (trainer_fault_id is null or answered_at is not null),
  check (verdict is null or answered_at is not null),
  check ((verdict is null) = (graded_at is null))
);
create index if not exists grading_assignments_trainer on public.grading_assignments (trainer_id, assigned_at desc);

alter table public.grading_assignments enable row level security;
-- The API uses a server-side connection; signed-in trainers may read their own assignments and admins all of them.
-- Trainers get no read access to analyses, uploads or users, so they can't see our feedback or the lifter early.
drop policy if exists grading_assignments_read on public.grading_assignments;
create policy grading_assignments_read on public.grading_assignments for select to authenticated
  using (trainer_id = auth.uid() or public.is_admin());
