import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import build_test_services


@pytest.fixture
def services():
    """In-memory auth, database and storage; synthetic video backend; rule-following fake LLM."""
    return build_test_services()


@pytest.fixture
def client(services):
    with TestClient(create_app(services)) as c:
        yield c
