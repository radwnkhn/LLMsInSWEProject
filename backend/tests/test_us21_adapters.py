"""US-21: production storage/auth API contracts, without real network calls."""
import json

import httpx
import pytest

from app.auth import SupabaseAuth
from app.storage import InMemoryStorage, SupabaseStorage


def test_us21_storage_removes_files_via_the_storage_api_in_idempotent_batches():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=[])
    storage = SupabaseStorage("https://example.supabase.co", "service-key", "videos",
                              http=httpx.Client(transport=httpx.MockTransport(handler)))
    paths = [f"u/{i}.mp4" for i in range(1001)]
    storage.delete(paths)
    assert [len(json.loads(r.content)["prefixes"]) for r in requests] == [1000, 1]
    assert all(r.method == "DELETE" and r.url.path == "/storage/v1/object/videos" for r in requests)
    assert all(r.headers["authorization"] == "Bearer service-key" for r in requests)
    assert [p for r in requests for p in json.loads(r.content)["prefixes"]] == paths


def test_us21_storage_lists_every_page_under_the_exact_account_prefix():
    seen = []
    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        assert request.method == "POST" and request.url.path == "/storage/v1/object/list/videos"
        return httpx.Response(200, json=[{"id": str(i), "name": f"{i}.mp4"} for i in range(1000)]
                              if payload["offset"] == 0 else [{"id": "last", "name": "last.mp4"}])
    storage = SupabaseStorage("https://example.supabase.co", "key", "videos",
                              http=httpx.Client(transport=httpx.MockTransport(handler)))
    assert len(storage.list_paths("user/")) == 1001
    assert all(p["prefix"] == "user/" for p in seen)
    assert [p["offset"] for p in seen] == [0, 1000]


def test_us21_storage_deletion_failure_is_not_reported_as_success():
    storage = SupabaseStorage("https://example.supabase.co", "key", "videos",
                              http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    with pytest.raises(httpx.HTTPStatusError):
        storage.delete(["u/a.mp4"])


def test_us21_in_memory_storage_deletion_is_idempotent_and_prefix_bounded():
    storage = InMemoryStorage()
    storage.upload("user/a.mp4", b"a", "video/mp4")
    storage.upload("user-other/b.mp4", b"b", "video/mp4")
    assert storage.list_paths("user/") == ["user/a.mp4"]
    storage.delete(["user/a.mp4", "missing"])
    storage.delete(["user/a.mp4"])
    assert set(storage.objects) == set(storage.content_types) == {"user-other/b.mp4"}


def test_us21_supabase_hard_deletes_auth_user_with_server_service_key():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={})
    auth = SupabaseAuth("https://example.supabase.co", "anon", service_key="secret-service-key",
                        http=httpx.Client(transport=httpx.MockTransport(handler)))
    auth.delete_user("user-id")
    assert requests[0].method == "DELETE" and requests[0].url.path == "/auth/v1/admin/users/user-id"
    assert requests[0].headers["authorization"] == "Bearer secret-service-key"
    assert json.loads(requests[0].content) == {"should_soft_delete": False}


def test_us21_missing_service_key_cannot_silently_delete_an_auth_user():
    auth = SupabaseAuth("https://example.supabase.co", "anon",
                        http=httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail("Must not call admin API with anon key"))))
    with pytest.raises(RuntimeError, match="service"):
        auth.delete_user("user-id")
