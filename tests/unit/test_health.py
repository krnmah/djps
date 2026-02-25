from fastapi.testclient import TestClient

def test_health_endpoint_returns_ok(app):
    """
    GIVEN: the fastAPI app
    When we call GET /health
    Then it should return 200 and the expected JSON payload.
    """
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}