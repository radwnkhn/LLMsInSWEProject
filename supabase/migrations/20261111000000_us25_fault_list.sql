-- US-25: the fault list admins manage. Seeded with the Alpha definitions from backend/app/faults.py
-- (FAULTS), so analyses behave exactly as before until an admin edits, disables or adds a fault.
-- Every Fault field is stored, threshold included, so US-24 can make thresholds editable without
-- another schema change. Faults are never deleted: saved analyses refer to them by (lift, id).
create table if not exists public.faults (
  lift text not null check (lift in ('squat', 'deadlift', 'bench_press')),
  id text not null check (id ~ '^[a-z][a-z0-9_]{2,39}$'),
  name text not null check (length(btrim(name)) between 1 and 80),
  short_name text not null check (length(btrim(short_name)) between 1 and 40),
  category text not null check (category in ('safety', 'technique')),
  metric text not null,
  metric_label text not null,
  threshold double precision not null,
  direction text not null check (direction in ('above', 'below')),
  unit text not null default '',
  views text[] not null,
  joints text[] not null,
  label_format text not null,
  enabled boolean not null default true,
  position integer not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (lift, id)
);

alter table public.faults enable row level security;
-- The API uses a server-side connection; signed-in admins may read the list directly too.
drop policy if exists faults_admin_read on public.faults;
create policy faults_admin_read on public.faults for select to authenticated using (public.is_admin());

insert into public.faults (lift, id, name, short_name, category, metric, metric_label, threshold, direction, unit,
                           views, joints, label_format, position) values
  ('squat', 'knee_cave', 'Knees cave inward', 'knee cave', 'safety', 'knee_valgus_deg', 'valgus', 10.0, 'above', '°', array['front']::text[], array['hips', 'knees', 'ankles']::text[], 'Valgus {value:.0f}°', 1),
  ('squat', 'hips_rise_early', 'Hips rise before your shoulders', 'hips rising early', 'technique', 'torso_lean_increase_deg', 'torso lean increase', 10.0, 'above', '°', array['side']::text[], array['shoulders', 'hips']::text[], 'Torso +{value:.0f}°', 2),
  ('squat', 'insufficient_depth', 'Squat isn''t reaching depth', 'shallow depth', 'technique', 'depth_margin', 'hip depth below the knee', 0.0, 'below', '', array['side', 'front', 'angled']::text[], array['hips', 'knees']::text[], 'Hip {value:+.2f} thigh below knee', 3),
  ('squat', 'excessive_forward_lean', 'Chest drops too far forward', 'forward lean', 'technique', 'torso_lean_max_deg', 'torso lean', 55.0, 'above', '°', array['side']::text[], array['shoulders', 'hips']::text[], 'Torso {value:.0f}°', 4),
  ('squat', 'bar_path_drift', 'Bar drifts forward and back', 'bar drift', 'technique', 'bar_drift_ratio', 'bar drift', 0.25, 'above', '', array['side']::text[], array['shoulders', 'hips', 'knees']::text[], 'Bar drift {value:.2f}', 5),
  ('deadlift', 'rounded_back', 'Your back rounds during the pull', 'rounded back', 'safety', 'back_rounding_deg', 'back rounding', 20.0, 'above', '°', array['side']::text[], array['ears', 'shoulders', 'hips']::text[], 'Back {value:.0f}°', 6),
  ('deadlift', 'hips_rise_early', 'Hips shoot up before the bar leaves the floor', 'hips rising early', 'technique', 'torso_lean_increase_deg', 'torso lean increase', 10.0, 'above', '°', array['side']::text[], array['shoulders', 'hips']::text[], 'Torso +{value:.0f}°', 7),
  ('deadlift', 'bar_path_drift', 'Bar drifts away from your legs', 'bar drift', 'technique', 'bar_drift_ratio', 'bar drift', 0.15, 'above', '', array['side']::text[], array['wrists', 'hips', 'knees']::text[], 'Bar drift {value:.2f}', 8),
  ('deadlift', 'incomplete_lockout', 'Hips don''t fully lock out at the top', 'incomplete lockout', 'technique', 'lockout_hip_angle_deg', 'hip angle at lockout', 165.0, 'below', '°', array['side']::text[], array['shoulders', 'hips', 'knees']::text[], 'Hip {value:.0f}°', 9),
  ('bench_press', 'elbow_flare', 'Elbows flare out too wide', 'elbow flare', 'safety', 'elbow_flare_deg', 'elbow flare', 75.0, 'above', '°', array['front']::text[], array['shoulders', 'elbows', 'hips']::text[], 'Flare {value:.0f}°', 10),
  ('bench_press', 'bar_path_drift', 'Bar drifts toward your face or belly', 'bar drift', 'technique', 'bar_drift_ratio', 'bar drift', 0.25, 'above', '', array['side']::text[], array['wrists', 'hips', 'knees']::text[], 'Bar drift {value:.2f}', 11),
  ('bench_press', 'incomplete_lockout', 'Arms don''t fully lock out', 'incomplete lockout', 'technique', 'lockout_elbow_angle_deg', 'elbow angle at lockout', 160.0, 'below', '°', array['side']::text[], array['shoulders', 'elbows', 'wrists']::text[], 'Elbow {value:.0f}°', 12),
  ('bench_press', 'uneven_press', 'Bar presses unevenly', 'uneven press', 'technique', 'wrist_height_diff_ratio', 'wrist height difference', 0.1, 'above', '', array['front']::text[], array['wrists', 'shoulders']::text[], 'Uneven {value:.2f}', 13)
on conflict (lift, id) do nothing;
