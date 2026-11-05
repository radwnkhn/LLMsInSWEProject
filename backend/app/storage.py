"""Private video and frame storage. SupabaseStorage in production; InMemoryStorage for tests and test mode."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import BinaryIO, Protocol
from urllib.parse import quote

import httpx


class Storage(Protocol):
    def upload(self, path: str, data: bytes | BinaryIO, content_type: str) -> None: ...
    def download(self, path: str) -> bytes: ...
    def signed_url(self, path: str, expires_in: int = 3600) -> str: ...


class SupabaseStorage:
    """Supabase Storage over its REST API, using the service-role key. The bucket is private, so every link
    handed to a browser is a short-lived signed URL."""

    def __init__(self, url: str, service_key: str, bucket: str, http: httpx.Client | None = None):
        self.base = f"{url.rstrip('/')}/storage/v1"
        self.bucket = bucket
        self.headers = {"Authorization": f"Bearer {service_key}", "apikey": service_key}
        self.http = http or httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0))

    def _object(self, path: str) -> str:
        return f"{self.base}/object/{self.bucket}/{quote(path)}"

    def upload(self, path, data, content_type):
        r = self.http.post(self._object(path), content=data,
                           headers={**self.headers, "Content-Type": content_type, "x-upsert": "true"})
        r.raise_for_status()

    def download(self, path):
        r = self.http.get(f"{self.base}/object/authenticated/{self.bucket}/{quote(path)}", headers=self.headers)
        r.raise_for_status()
        return r.content

    def signed_url(self, path, expires_in=3600):
        r = self.http.post(f"{self.base}/object/sign/{self.bucket}/{quote(path)}", json={"expiresIn": expires_in},
                           headers=self.headers)
        r.raise_for_status()
        return f"{self.base}{r.json()['signedURL']}"


class InMemoryStorage:
    """Keeps objects in a dict. Signed URLs point at the test-mode /test-storage route and carry an HMAC token."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}
        self._secret = secrets.token_bytes(16)

    def upload(self, path, data, content_type):
        self.objects[path] = data if isinstance(data, bytes) else data.read()
        self.content_types[path] = content_type

    def download(self, path):
        return self.objects[path]

    def token_for(self, path: str) -> str:
        return hmac.new(self._secret, path.encode(), hashlib.sha256).hexdigest()

    def signed_url(self, path, expires_in=3600):
        return f"/test-storage/{quote(path)}?token={self.token_for(path)}"
