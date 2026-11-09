"""US-21: confirmation, ownership, complete cleanup, and retryable failures."""
import uuid
from threading import Event, Thread

import httpx
import pytest

from tests.helpers import PASSWORD, make_admin, signup, upload_ok


def remove(client, path, headers=None, body=None):
    return client.request("DELETE", path, headers=headers or {}, json={"confirmed": True} if body is None else body)


def owned_upload(client, services, headers):
    aid = upload_ok(client, headers)
    a = services.repo.get_analysis(aid)
    result = client.get(f"/analyses/{aid}", headers=headers).json()
    return a.upload_id, aid, result


def test_us21_delete_upload_removes_media_results_measurements_attempts_and_feedback(client, services):
    headers, uid = signup(client)
    upload_id, aid, result = owned_upload(client, services, headers)
    client.post(f"/analyses/{aid}/feedback", headers=headers, json={"rating": 4})
    assert services.repo.list_rep_measurements(aid) and services.repo.list_llm_attempts(aid)
    response = remove(client, f"/uploads/{upload_id}", headers)
    assert response.status_code == 204 and not response.content
    assert services.repo.get_upload(upload_id) is None and services.repo.get_analysis(aid) is None
    assert services.repo.list_rep_measurements(aid) == services.repo.list_llm_attempts(aid) == []
    assert services.repo.get_feedback(aid, uid) is None
    assert not services.storage.objects and not services.storage.content_types
    assert client.get("/history", headers=headers).json()["items"] == []
    assert client.get(f"/analyses/{aid}", headers=headers).status_code == 404
    assert client.post(f"/analyses/{aid}/retry", headers=headers).status_code == 404
    for url in [result["video_url"], result["annotated_frame"]["image_url"]]:
        assert client.get(url).status_code != 200


def test_us21_deleting_one_upload_keeps_the_other_users_and_uploads(client, services):
    headers, _ = signup(client)
    other, _ = signup(client, "other@virginia.edu")
    upload_id, aid, _ = owned_upload(client, services, headers)
    kept = upload_ok(client, headers, filename="clean.mp4")
    private = upload_ok(client, other)
    assert remove(client, f"/uploads/{upload_id}", headers).status_code == 204
    assert client.get(f"/analyses/{kept}", headers=headers).status_code == 200
    assert client.get(f"/analyses/{private}", headers=other).status_code == 200
    assert client.get("/comparisons", params={"first_id": aid, "second_id": kept}, headers=headers).status_code == 404


def test_us21_deletion_also_removes_all_retries_and_partial_frames(client, services):
    headers, uid = signup(client)
    upload_id, aid, _ = owned_upload(client, services, headers)
    retry = str(uuid.uuid4())
    services.repo.create_analysis(retry, upload_id, uid, "squat")
    services.repo.update_analysis(retry, status="failed", error="partial failure")
    path = f"frames/{uid}/{retry}.png"
    services.storage.upload(path, b"frame created before failure", "image/png")
    assert remove(client, f"/uploads/{upload_id}", headers).status_code == 204
    assert services.repo.get_analysis(retry) is None
    assert path not in services.storage.objects


@pytest.mark.parametrize("path", ["/uploads/missing", "/account"])
def test_us21_deletion_requires_a_valid_session(client, path):
    assert remove(client, path).status_code == 401
    assert remove(client, path, {"Authorization": "Bearer invalid"}).status_code == 401


def test_us21_users_cannot_delete_someone_elses_upload_even_as_admin(client, services):
    owner, _ = signup(client)
    other, _ = make_admin(client, services)
    upload_id, aid, _ = owned_upload(client, services, owner)
    assert remove(client, f"/uploads/{upload_id}", other).status_code == 404
    assert client.get(f"/analyses/{aid}", headers=owner).status_code == 200


@pytest.mark.parametrize("body", [{}, {"confirmed": False}, {"confirmed": "true"}, {"confirmed": 1}])
def test_us21_api_requires_explicit_boolean_confirmation_before_any_delete(client, services, body):
    headers, uid = signup(client)
    upload_id, aid, _ = owned_upload(client, services, headers)
    for path in (f"/uploads/{upload_id}", "/account"):
        assert remove(client, path, headers, body).status_code == 422
    assert services.repo.get_user(uid) and services.repo.get_analysis(aid)
    assert services.storage.objects


@pytest.mark.parametrize("status", ["queued", "processing"])
def test_us21_processing_must_finish_before_upload_or_account_cleanup(client, services, status):
    headers, uid = signup(client)
    upload_id, aid, _ = owned_upload(client, services, headers)
    services.repo.update_analysis(aid, status=status)
    for path in (f"/uploads/{upload_id}", "/account"):
        response = remove(client, path, headers)
        assert response.status_code == 409 and "finish" in response.json()["detail"].lower()
    assert services.repo.get_user(uid) and services.storage.objects


def test_us21_storage_failure_retains_records_for_a_successful_retry(client, services, monkeypatch):
    headers, _ = signup(client)
    upload_id, aid, _ = owned_upload(client, services, headers)
    delete = getattr(services.storage, "delete", None)

    def fail(_paths):
        raise httpx.ConnectError("private credentials must not leak")

    monkeypatch.setattr(services.storage, "delete", fail, raising=False)
    response = remove(client, f"/uploads/{upload_id}", headers)
    assert response.status_code == 502 and "private credentials" not in response.text
    assert services.repo.get_analysis(aid) is not None
    assert delete is not None
    monkeypatch.setattr(services.storage, "delete", delete)
    assert remove(client, f"/uploads/{upload_id}", headers).status_code == 204


def test_us21_deleted_upload_is_absent_from_admin_inspection_and_error_summaries(client, services):
    headers, _ = signup(client)
    admin, _ = make_admin(client, services)
    upload_id, aid, _ = owned_upload(client, services, headers)
    assert remove(client, f"/uploads/{upload_id}", headers).status_code == 204
    assert client.get(f"/admin/analyses/{aid}", headers=admin).status_code == 404
    assert aid not in str(client.get("/admin/analyses", headers=admin).json())


def test_us21_delete_account_removes_all_owned_data_orphans_and_every_session(client, services):
    headers, uid = signup(client)
    token2 = client.post("/auth/login", json={"email": "lifter@virginia.edu", "password": PASSWORD}).json()["access_token"]
    _, aid, result = owned_upload(client, services, headers)
    upload_ok(client, headers, filename="clean.mp4")
    services.storage.upload(f"{uid}/orphan.mp4", b"orphan", "video/mp4")
    services.storage.upload(f"frames/{uid}/orphan.png", b"orphan", "image/png")
    other, other_id = signup(client, "other@virginia.edu")
    other_aid = upload_ok(client, other)
    response = remove(client, "/account", headers)
    assert response.status_code == 204
    assert services.repo.get_user(uid) is None
    assert services.repo.list_analyses_for_user(uid) == []
    assert not any(key.startswith(f"{uid}/") or key.startswith(f"frames/{uid}/") for key in services.storage.objects)
    for session in [headers, {"Authorization": "Bearer " + token2}]:
        assert client.get("/auth/me", headers=session).status_code == 401
        assert client.get("/history", headers=session).status_code == 401
    assert client.post("/auth/login", json={"email": "lifter@virginia.edu", "password": PASSWORD}).status_code == 401
    assert services.repo.get_user(uid) is None, "Stale sessions must not recreate the profile"
    assert services.repo.get_user(other_id) and client.get(f"/analyses/{other_aid}", headers=other).status_code == 200
    assert client.get(result["video_url"]).status_code != 200


def test_us21_account_with_no_uploads_can_be_deleted(client, services):
    headers, uid = signup(client)
    assert remove(client, "/account", headers).status_code == 204
    assert services.repo.get_user(uid) is None


def test_us21_account_storage_failure_does_not_revoke_the_session_or_erase_records(client, services, monkeypatch):
    headers, uid = signup(client)
    _, aid, _ = owned_upload(client, services, headers)
    monkeypatch.setattr(services.storage, "delete", lambda paths: (_ for _ in ()).throw(httpx.ConnectError("offline")), raising=False)
    assert remove(client, "/account", headers).status_code == 502
    assert services.repo.get_user(uid) and services.repo.get_analysis(aid)
    assert client.get("/auth/me", headers=headers).status_code == 200


def test_us21_auth_service_failure_returns_an_error_and_can_be_retried(client, services, monkeypatch):
    headers, _ = signup(client)
    delete = getattr(services.auth, "delete_user", None)
    monkeypatch.setattr(services.auth, "delete_user", lambda uid: (_ for _ in ()).throw(httpx.ConnectError("offline")), raising=False)
    assert remove(client, "/account", headers).status_code == 502
    assert delete is not None
    monkeypatch.setattr(services.auth, "delete_user", delete)
    assert remove(client, "/account", headers).status_code == 204


def test_us21_history_exposes_upload_id_for_deleting_the_entire_upload(client, services):
    headers, _ = signup(client)
    upload_id, _, _ = owned_upload(client, services, headers)
    assert client.get("/history", headers=headers).json()["items"][0]["upload_id"] == upload_id


def test_us21_concurrent_retry_cannot_recreate_a_deleted_account_or_upload(client, services, monkeypatch):
    headers, uid = signup(client)
    _, aid, _ = owned_upload(client, services, headers)
    services.repo.update_analysis(aid, status="failed")
    entered, proceed, authenticated = Event(), Event(), Event()
    delete = getattr(services.storage, "delete", lambda paths: None)
    get_user = services.auth.get_user
    outcomes = {}

    def hold(paths):
        entered.set()
        if not proceed.wait(8):
            raise TimeoutError("Test did not release deletion")
        delete(paths)

    monkeypatch.setattr(services.storage, "delete", hold, raising=False)
    deleting = Thread(target=lambda: outcomes.update(deleted=remove(client, "/account", headers).status_code), daemon=True)
    retrying = Thread(target=lambda: outcomes.update(retried=client.post(f"/analyses/{aid}/retry", headers=headers).status_code), daemon=True)
    deleting.start()
    try:
        assert entered.wait(3), "Deletion never reached storage cleanup"
        def observe_auth(token):
            user = get_user(token)
            if user is not None:
                authenticated.set()
            return user
        monkeypatch.setattr(services.auth, "get_user", observe_auth)
        retrying.start()
        assert authenticated.wait(3), "Retry never authenticated before deletion completed"
    finally:
        proceed.set()
        deleting.join(8)
        if retrying.ident:
            retrying.join(8)
    assert not deleting.is_alive() and not retrying.is_alive()
    assert outcomes == {"deleted": 204, "retried": 401}
    assert services.repo.get_user(uid) is None and services.repo.list_analyses_for_user(uid) == []
