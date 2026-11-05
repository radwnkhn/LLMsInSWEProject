"""US-01: Sign up and log in. (The logout redirect is an e2e test: frontend/e2e/us01-auth.spec.ts.)"""
import httpx
import pytest

from app.auth import InvalidCredentials, SupabaseAuth
from tests.helpers import PASSWORD, signup, upload_ok

PROTECTED = [
    ("post", "/uploads"),
    ("get", "/analyses/00000000-0000-0000-0000-000000000000"),
    ("get", "/history"),
    ("post", "/analyses/00000000-0000-0000-0000-000000000000/feedback"),
    ("get", "/auth/me"),
]


# ---- [integration] sign up with a valid email and an 8+ character password ----

def test_us01_signup_creates_account_and_logs_in(client):
    r = client.post("/auth/signup", json={"email": "lifter@virginia.edu", "password": PASSWORD})
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"]
    assert body["user"]["email"] == "lifter@virginia.edu"
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "lifter@virginia.edu"


def test_us01_password_of_exactly_8_characters_is_enough(client):
    r = client.post("/auth/signup", json={"email": "eight@virginia.edu", "password": "12345678"})
    assert r.status_code == 201


@pytest.mark.parametrize("email,password", [
    ("not-an-email", PASSWORD),
    ("missing@tld", PASSWORD),
    ("", PASSWORD),
    ("lifter@virginia.edu", "1234567"),
    ("lifter@virginia.edu", ""),
])
def test_us01_signup_rejects_bad_email_or_short_password(client, email, password):
    r = client.post("/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 422


def test_us01_signup_with_existing_email_is_rejected(client):
    signup(client)
    r = client.post("/auth/signup", json={"email": "lifter@virginia.edu", "password": PASSWORD})
    assert r.status_code == 409


def test_us01_email_is_case_insensitive(client):
    signup(client, "Lifter@Virginia.edu")
    r = client.post("/auth/login", json={"email": "lifter@virginia.edu", "password": PASSWORD})
    assert r.status_code == 200


# ---- [integration] wrong password ----

def test_us01_wrong_password_is_rejected_with_message(client):
    signup(client)
    r = client.post("/auth/login", json={"email": "lifter@virginia.edu", "password": "wrong-password"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Incorrect email or password"}
    assert "access_token" not in r.json()


def test_us01_unknown_email_gets_the_same_message(client):
    r = client.post("/auth/login", json={"email": "nobody@virginia.edu", "password": PASSWORD})
    assert r.status_code == 401
    assert r.json() == {"detail": "Incorrect email or password"}


def test_us01_correct_password_logs_in(client):
    signup(client)
    r = client.post("/auth/login", json={"email": "lifter@virginia.edu", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["access_token"]


# ---- [integration] protected endpoints return 401 without a login ----

@pytest.mark.parametrize("method,path", PROTECTED)
def test_us01_protected_endpoints_require_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED)
def test_us01_protected_endpoints_reject_invalid_tokens(client, method, path):
    r = getattr(client, method)(path, headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_us01_logged_out_token_no_longer_works(client):
    headers, _ = signup(client)
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401


# ---- [integration] uploads and analyses are saved with the user's ID ----

def test_us01_upload_and_analysis_saved_with_user_id(client, services):
    headers, user_id = signup(client)
    analysis_id = upload_ok(client, headers)
    analysis = services.repo.get_analysis(analysis_id)
    assert analysis.user_id == user_id
    assert services.repo.get_upload(analysis.upload_id).user_id == user_id


# ---- Supabase Auth adapter (used in production) ----

def _supabase(handler):
    return SupabaseAuth("https://abc.supabase.co", "anon-key", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_us01_supabase_signup_returns_session():
    def handler(request):
        assert request.url.path == "/auth/v1/signup"
        assert request.headers["apikey"] == "anon-key"
        return httpx.Response(200, json={"access_token": "tok", "user": {"id": "u1", "email": "a@b.edu", "app_metadata": {}}})

    session = _supabase(handler).sign_up("a@b.edu", PASSWORD)
    assert session.access_token == "tok"
    assert session.user.id == "u1"
    assert session.user.is_admin is False


def test_us01_supabase_wrong_password_raises_invalid_credentials():
    def handler(request):
        assert request.url.path == "/auth/v1/token"
        assert request.url.params["grant_type"] == "password"
        return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Invalid login credentials"})

    with pytest.raises(InvalidCredentials):
        _supabase(handler).sign_in("a@b.edu", "wrong-password")


def test_us01_supabase_get_user_reads_admin_role():
    def handler(request):
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json={"id": "u1", "email": "coach@b.edu", "app_metadata": {"role": "admin"}})

    user = _supabase(handler).get_user("tok")
    assert user.is_admin is True


def test_us01_supabase_get_user_with_bad_token_returns_none():
    assert _supabase(lambda r: httpx.Response(401, json={"msg": "bad jwt"})).get_user("tok") is None
