import os
import pytest
from fastapi.testclient import TestClient

# Configure test settings before app import
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_nps_ivr.db")

from app.main import app  # noqa: E402
from app.db import init_db  # noqa: E402

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()
    yield
    # Clean up test DB file
    try:
        os.remove("test_nps_ivr.db")
    except FileNotFoundError:
        pass

@pytest.fixture()
def client():
    return TestClient(app)
