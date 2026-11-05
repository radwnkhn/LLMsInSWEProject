"""SETUP-02: Database, storage and deployment.

The live Postgres tests run when TEST_DATABASE_URL points at a disposable Postgres database
(CI starts one). They wipe the public, auth and storage schemas of that database.
The deployment check is a Playwright test: frontend/e2e/setup02-deploy.spec.ts.
"""
import json
import os
import re
import uuid
from pathlib import Path

import httpx
import pytest

from app.storage import SupabaseStorage
from tests.helpers import signup, upload_ok

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
STUB = Path(__file__).parent / "fixtures" / "supabase_stub.sql"
TABLES = ["users", "uploads", "analyses", "rep_measurements", "llm_attempts", "validation_results", "feedback_responses"]


def _sql():
    return "\n".join(p.read_text() for p in MIGRATIONS).lower()


# ---- [integration] checked-in migration creates the tables ----

def test_setup02_migration_is_checked_in():
    assert MIGRATIONS, "expected at least one .sql file in supabase/migrations"


@pytest.mark.parametrize("table", TABLES)
def test_setup02_migration_creates_table(table):
    assert re.search(rf"create table (if not exists )?public\.{table}\s*\(", _sql())


@pytest.mark.parametrize("table", TABLES)
def test_setup02_rls_enabled_on_every_table(table):
    assert re.search(rf"alter table public\.{table} enable row level security", _sql())


def test_setup02_storage_bucket_is_private():
    m = re.search(r"insert into storage\.buckets\s*\(id, name, public\)\s*values\s*\('videos',\s*'videos',\s*false\)", _sql())
    assert m, "the videos bucket must be created with public = false"


# ---- live Postgres: migration + row-level security ----

PG_URL = os.environ.get("TEST_DATABASE_URL")
needs_pg = pytest.mark.skipif(not PG_URL, reason="set TEST_DATABASE_URL to run the Postgres tests")


@pytest.fixture
def pg():
    import psycopg

    conn = psycopg.connect(PG_URL, autocommit=True)
    conn.execute("drop schema if exists public cascade; drop schema if exists auth cascade; "
                 "drop schema if exists storage cascade; create schema public;")
    conn.execute(STUB.read_text())
    for path in MIGRATIONS:
        conn.execute(path.read_text())
    yield conn
    conn.execute("reset role")
    conn.close()


def _seed(conn):
    a, b, admin = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    for uid, email in ((a, "a@virginia.edu"), (b, "b@virginia.edu"), (admin, "coach@virginia.edu")):
        conn.execute("insert into auth.users (id, email) values (%s, %s)", (uid, email))
    conn.execute("update public.users set is_admin = true where id = %s", (admin,))
    for uid in (a, b):
        up = uuid.uuid4()
        conn.execute("insert into public.uploads (id, user_id, lift, video_path, filename) values (%s, %s, 'squat', %s, 'set.mp4')",
                     (up, uid, f"{uid}/{up}.mp4"))
        conn.execute("insert into public.analyses (id, upload_id, user_id, lift) values (%s, %s, %s, 'squat')",
                     (uuid.uuid4(), up, uid))
    return a, b, admin


def _as_user(conn, uid):
    conn.execute("set role authenticated")
    conn.execute("select set_config('request.jwt.claims', %s, false)", (json.dumps({"sub": str(uid), "role": "authenticated"}),))


@needs_pg
def test_setup02_migration_applies_cleanly(pg):
    rows = pg.execute("select table_name from information_schema.tables where table_schema = 'public'").fetchall()
    assert set(TABLES) <= {r[0] for r in rows}


@needs_pg
def test_setup02_rls_user_reads_only_own_uploads_and_analyses(pg):
    a, b, _ = _seed(pg)
    _as_user(pg, a)
    assert {r[0] for r in pg.execute("select user_id from public.uploads").fetchall()} == {a}
    assert {r[0] for r in pg.execute("select user_id from public.analyses").fetchall()} == {a}


@needs_pg
def test_setup02_rls_admin_reads_all(pg):
    a, b, admin = _seed(pg)
    _as_user(pg, admin)
    assert {r[0] for r in pg.execute("select user_id from public.uploads").fetchall()} == {a, b}
    assert {r[0] for r in pg.execute("select user_id from public.analyses").fetchall()} == {a, b}


@needs_pg
def test_setup02_rls_user_cannot_insert_rows_for_someone_else(pg):
    import psycopg

    a, b, _ = _seed(pg)
    _as_user(pg, a)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        pg.execute("insert into public.uploads (id, user_id, lift, video_path, filename) values (%s, %s, 'squat', 'x', 'x.mp4')",
                   (uuid.uuid4(), b))


@needs_pg
def test_setup02_rls_anonymous_reads_nothing(pg):
    _seed(pg)
    pg.execute("set role anon")
    with pytest.raises(Exception):
        pg.execute("select * from public.uploads").fetchall()


# ---- [integration] videos and annotated frames go to a private Supabase Storage bucket ----

def _recording_storage():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if "/object/sign/" in request.url.path:
            return httpx.Response(200, json={"signedURL": "/object/sign/videos/u1/a.mp4?token=abc"})
        return httpx.Response(200, json={"Key": "videos/u1/a.mp4"})

    storage = SupabaseStorage("https://abc.supabase.co", "service-key", "videos",
                              http=httpx.Client(transport=httpx.MockTransport(handler)))
    return storage, calls


def test_setup02_supabase_storage_uploads_into_videos_bucket_with_service_key():
    storage, calls = _recording_storage()
    storage.upload("u1/a.mp4", b"data", "video/mp4")
    req = calls[0]
    assert req.method == "POST"
    assert str(req.url) == "https://abc.supabase.co/storage/v1/object/videos/u1/a.mp4"
    assert req.headers["authorization"] == "Bearer service-key"
    assert req.headers["content-type"] == "video/mp4"
    assert req.content == b"data"


def test_setup02_supabase_storage_hands_out_signed_urls_not_public_ones():
    storage, calls = _recording_storage()
    url = storage.signed_url("u1/a.mp4", expires_in=600)
    assert url == "https://abc.supabase.co/storage/v1/object/sign/videos/u1/a.mp4?token=abc"
    assert calls[0].url.path == "/storage/v1/object/sign/videos/u1/a.mp4"
    assert json.loads(calls[0].content) == {"expiresIn": 600}
    assert all("/object/public/" not in str(c.url) for c in calls)


def test_setup02_storage_errors_raise():
    storage = SupabaseStorage("https://abc.supabase.co", "k", "videos",
                              http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403, json={"error": "nope"}))))
    with pytest.raises(Exception):
        storage.upload("u1/a.mp4", b"data", "video/mp4")


def test_setup02_video_and_annotated_frame_saved_to_storage(client, services):
    headers, user_id = signup(client)
    analysis_id = upload_ok(client, headers)
    keys = list(services.storage.objects)
    assert any(k.startswith(f"{user_id}/") and k.endswith(".mp4") for k in keys)
    assert any(k.startswith(f"frames/{user_id}/{analysis_id}") and k.endswith(".png") for k in keys)
    result = client.get(f"/analyses/{analysis_id}", headers=headers).json()
    # Media is only reachable through short-lived signed links.
    assert "token=" in result["video_url"]
    assert "token=" in result["annotated_frame"]["image_url"]
