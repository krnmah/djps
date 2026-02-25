import pytest

from app.main import create_app

@pytest.fixture(scope="session")
def app():
    """
    Returns a FastAPI app instance for tests.
    """
    return create_app()