from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers import PricingProvider


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def mock_provider() -> MagicMock:
    mock = MagicMock(spec=PricingProvider)
    return mock
