"""Email + password accounts. SupabaseAuth in production; InMemoryAuth for tests and test mode."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from urllib.parse import quote
from dataclasses import dataclass
from typing import Protocol

import httpx


class InvalidCredentials(Exception):
    pass


class EmailTaken(Exception):
    pass


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    is_admin: bool = False


@dataclass(frozen=True)
class Session:
    access_token: str
    user: AuthUser


class AuthProvider(Protocol):
    def sign_up(self, email: str, password: str) -> Session: ...
    def sign_in(self, email: str, password: str) -> Session: ...
    def sign_out(self, token: str) -> None: ...
    def get_user(self, token: str) -> AuthUser | None: ...
    def delete_user(self, user_id: str) -> None: ...


class SupabaseAuth:
    """Supabase Auth (GoTrue) REST API. Admins have app_metadata.role = "admin" (set in the Supabase dashboard)."""

    def __init__(self, url: str, anon_key: str, http: httpx.Client | None = None, service_key: str | None = None):
        self.base = f"{url.rstrip('/')}/auth/v1"
        self.anon_key = anon_key
        self.service_key = service_key
        self.http = http or httpx.Client(timeout=httpx.Timeout(15.0))

    @staticmethod
    def _user(data: dict) -> AuthUser:
        role = (data.get("app_metadata") or {}).get("role")
        return AuthUser(id=data["id"], email=data.get("email", ""), is_admin=role == "admin")

    def sign_up(self, email, password):
        r = self.http.post(f"{self.base}/signup", headers={"apikey": self.anon_key},
                           json={"email": email, "password": password})
        if r.status_code in (400, 422) and "already" in r.text.lower():
            raise EmailTaken(email)
        r.raise_for_status()
        data = r.json()
        if not data.get("access_token"):
            # Email confirmation is on in Supabase: no session until confirmed. Try logging in anyway.
            return self.sign_in(email, password)
        return Session(data["access_token"], self._user(data["user"]))

    def sign_in(self, email, password):
        r = self.http.post(f"{self.base}/token", params={"grant_type": "password"}, headers={"apikey": self.anon_key},
                           json={"email": email, "password": password})
        if r.status_code in (400, 401):
            raise InvalidCredentials()
        r.raise_for_status()
        data = r.json()
        return Session(data["access_token"], self._user(data["user"]))

    def sign_out(self, token):
        self.http.post(f"{self.base}/logout", headers={"apikey": self.anon_key, "Authorization": f"Bearer {token}"})

    def get_user(self, token):
        try:
            r = self.http.get(f"{self.base}/user", headers={"apikey": self.anon_key, "Authorization": f"Bearer {token}"})
        except httpx.HTTPError:
            return None
        return self._user(r.json()) if r.status_code == 200 else None

    def delete_user(self, user_id):
        if not self.service_key:
            raise RuntimeError("Supabase service role key is required to delete an account")
        response = self.http.request("DELETE", f"{self.base}/admin/users/{quote(user_id, safe='')}",
                                     headers={"apikey": self.service_key, "Authorization": f"Bearer {self.service_key}"},
                                     json={"should_soft_delete": False})
        if response.status_code != 404:
            response.raise_for_status()


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 10_000)


class InMemoryAuth:
    def __init__(self):
        self.users: dict[str, dict] = {}       # email -> {id, salt, hash, is_admin}
        self.tokens: dict[str, str] = {}       # token -> email

    def _session(self, email: str) -> Session:
        token = secrets.token_urlsafe(24)
        self.tokens[token] = email
        u = self.users[email]
        return Session(token, AuthUser(u["id"], email, u["is_admin"]))

    def sign_up(self, email, password):
        email = email.lower()
        if email in self.users:
            raise EmailTaken(email)
        salt = secrets.token_bytes(8)
        self.users[email] = {"id": str(uuid.uuid4()), "salt": salt, "hash": _hash(password, salt), "is_admin": False}
        return self._session(email)

    def sign_in(self, email, password):
        email = email.lower()
        u = self.users.get(email)
        if not u or not secrets.compare_digest(u["hash"], _hash(password, u["salt"])):
            raise InvalidCredentials()
        return self._session(email)

    def sign_out(self, token):
        self.tokens.pop(token, None)

    def get_user(self, token):
        email = self.tokens.get(token)
        if not email:
            return None
        u = self.users.get(email)
        if u is None:
            return None
        return AuthUser(u["id"], email, u["is_admin"])

    def delete_user(self, user_id):
        emails = {email for email, user in list(self.users.items()) if user["id"] == user_id}
        for token, email in list(self.tokens.items()):
            if email in emails:
                self.tokens.pop(token, None)
        for email in emails:
            self.users.pop(email, None)

    def make_admin(self, user_id: str) -> None:
        for u in self.users.values():
            if u["id"] == user_id:
                u["is_admin"] = True
