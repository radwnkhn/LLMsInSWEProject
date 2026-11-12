-- US-24: a record of every fault threshold change. The thresholds themselves stay in public.faults (US-25);
-- the API saves a change and its log entry in one transaction. Faults are never deleted, so each entry keeps
-- pointing at its fault. If the admin's account is deleted later, the entry stays and the reference becomes null.
create table if not exists public.fault_threshold_changes (
  id bigint generated always as identity primary key,
  lift text not null,
  fault_id text not null,
  old_threshold double precision not null,
  new_threshold double precision not null,
  changed_by uuid references public.users (id) on delete set null,
  changed_at timestamptz not null default now(),
  foreign key (lift, fault_id) references public.faults (lift, id)
);
create index if not exists fault_threshold_changes_changed_at on public.fault_threshold_changes (changed_at desc);

alter table public.fault_threshold_changes enable row level security;
-- The API uses a server-side connection; signed-in admins may read the log directly too.
drop policy if exists fault_threshold_changes_admin_read on public.fault_threshold_changes;
create policy fault_threshold_changes_admin_read on public.fault_threshold_changes for select to authenticated using (public.is_admin());
