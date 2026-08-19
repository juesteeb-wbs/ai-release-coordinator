from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def api_key() -> str:
    return "test-api-key"


@pytest.fixture
def client(api_key: str) -> Iterator[TestClient]:
    database_dir = Path("test-tmp") / "databases"
    database_dir.mkdir(parents=True, exist_ok=True)
    database_path = database_dir / f"{uuid4()}.sqlite3"
    app = create_app(Settings(api_key=api_key, database_path=str(database_path)))

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key}


@pytest.fixture
def ticket_payload() -> dict[str, str]:
    return {
        "title": "Cannot access billing portal",
        "description": "The customer receives a permission error when opening invoices.",
        "customer_email": "alex@example.com",
        "category": "billing",
        "priority": "high",
    }
