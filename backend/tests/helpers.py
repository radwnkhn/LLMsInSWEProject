"""Small helpers shared by the API tests."""
from app.measure import measure_set
from app.rules import confirm_faults, not_measured_checks
from app.validator import build_validation_context

PASSWORD = "squat1234"


def signup(client, email="lifter@virginia.edu", password=PASSWORD):
    r = client.post("/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


def make_admin(client, services, email="coach@virginia.edu"):
    headers, user_id = signup(client, email)
    services.auth.make_admin(user_id)
    return headers, user_id


def upload(client, headers, lift="squat", filename="set.mp4", note=None,
           content=b"fake video bytes", content_type="video/mp4"):
    data = {"lift": lift}
    if note is not None:
        data["note"] = note
    return client.post("/uploads", headers=headers, data=data,
                       files={"file": (filename, content, content_type)})


def upload_ok(client, headers, **kwargs):
    r = upload(client, headers, **kwargs)
    assert r.status_code == 201, r.text
    return r.json()["analysis_id"]


def context_for(frames, lift="squat", note=None):
    m = measure_set(frames, lift, fps=30)
    nm = not_measured_checks(m)
    return build_validation_context(m, nm, confirm_faults(m, nm), note), m


def coach_output(ctx, measurements, top=None, reps=None, others=(), cue="Drive your chest up with your hips",
                 explanation="Keep the bar over your midfoot.", recommendation=None):
    """A reply that matches the measurements, citing `top` on `reps` and each (fault_id, reps) in `others`."""
    from app.faults import get_fault

    def supporting(fault_id, cited):
        fault = get_fault(ctx.lift, fault_id)
        rep = cited[0]
        return {"metric": fault.metric, "rep": rep, "value": measurements.reps[rep - 1].metrics[fault.metric]}

    out = {
        "lift": ctx.lift,
        "camera_angle": ctx.camera_angle,
        "rep_count": ctx.rep_count,
        "top_fault_id": top,
        "fault_reps": list(reps or []),
        "supporting_measurement": supporting(top, reps) if top else None,
        "other_faults": [{"fault_id": f, "reps": list(r), "supporting_measurement": supporting(f, r)} for f, r in others],
        "cue": cue if top else "",
        "explanation": explanation,
    }
    if recommendation is not None:
        out["professional_recommendation"] = recommendation
    return out
