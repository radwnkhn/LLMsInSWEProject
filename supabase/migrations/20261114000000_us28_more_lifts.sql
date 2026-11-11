-- US-28: overhead press and Romanian deadlift.
-- 1. Every table that stores a lift accepts the two new lifts.
-- 2. Their faults join the US-25 fault list, after any faults already there (seeded or added by an admin).
--    Thresholds are first guesses, to be tuned with trainer grading (US-22) and threshold editing (US-24);
--    the values come from backend/app/faults.py (FAULTS) and are explained in docs/tdd/us28.md.
alter table public.uploads drop constraint if exists uploads_lift_check;
alter table public.uploads add constraint uploads_lift_check check (lift in ('squat', 'deadlift', 'bench_press', 'overhead_press', 'romanian_deadlift'));
alter table public.analyses drop constraint if exists analyses_lift_check;
alter table public.analyses add constraint analyses_lift_check check (lift in ('squat', 'deadlift', 'bench_press', 'overhead_press', 'romanian_deadlift'));
alter table public.faults drop constraint if exists faults_lift_check;
alter table public.faults add constraint faults_lift_check check (lift in ('squat', 'deadlift', 'bench_press', 'overhead_press', 'romanian_deadlift'));
alter table public.moderation_log drop constraint if exists moderation_log_lift_check;
alter table public.moderation_log add constraint moderation_log_lift_check check (lift in ('squat', 'deadlift', 'bench_press', 'overhead_press', 'romanian_deadlift'));

insert into public.faults (lift, id, name, short_name, category, metric, metric_label, threshold, direction, unit,
                           views, joints, label_format, position)
select v.lift, v.id, v.name, v.short_name, v.category, v.metric, v.metric_label, v.threshold, v.direction, v.unit,
       v.views, v.joints, v.label_format, (select coalesce(max(position), 0) from public.faults) + v.ord
from (values
  ('overhead_press', 'excessive_back_arch', 'Lower back arches as you press', 'back arch', 'safety', 'torso_lean_back_max_deg', 'backward lean', 15.0, 'above', '°', array['side']::text[], array['shoulders', 'hips']::text[], 'Lean back {value:.0f}°', 1),
  ('overhead_press', 'bar_path_drift', 'Bar drifts forward away from your head', 'bar drift', 'technique', 'bar_drift_ratio', 'bar drift', 0.3, 'above', '', array['side']::text[], array['wrists', 'shoulders', 'hips']::text[], 'Bar drift {value:.2f}', 2),
  ('overhead_press', 'incomplete_lockout', 'Arms don''t fully lock out overhead', 'incomplete lockout', 'technique', 'lockout_elbow_angle_deg', 'elbow angle at lockout', 165.0, 'below', '°', array['side']::text[], array['shoulders', 'elbows', 'wrists']::text[], 'Elbow {value:.0f}°', 3),
  ('romanian_deadlift', 'rounded_back', 'Your back rounds as you hinge', 'rounded back', 'safety', 'back_rounding_deg', 'back rounding', 20.0, 'above', '°', array['side']::text[], array['ears', 'shoulders', 'hips']::text[], 'Back {value:.0f}°', 4),
  ('romanian_deadlift', 'knees_bend_too_much', 'Knees bend too much, turning it into a deadlift', 'knee bend', 'technique', 'knee_angle_min_deg', 'knee angle', 140.0, 'below', '°', array['side']::text[], array['hips', 'knees', 'ankles']::text[], 'Knee {value:.0f}°', 5),
  ('romanian_deadlift', 'bar_path_drift', 'Bar drifts away from your legs', 'bar drift', 'technique', 'bar_drift_ratio', 'bar drift', 0.15, 'above', '', array['side']::text[], array['wrists', 'hips', 'knees']::text[], 'Bar drift {value:.2f}', 6)
) as v(lift, id, name, short_name, category, metric, metric_label, threshold, direction, unit, views, joints,
       label_format, ord)
on conflict (lift, id) do nothing;
