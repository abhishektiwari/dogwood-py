import pytest

from dogwood import native


def test_fastapi_native_example_authorizes_requests():
    if not native.available():
        pytest.skip("native extension is not built")

    try:
        from fastapi.testclient import TestClient
    except Exception:
        pytest.skip("FastAPI example dependencies are not installed")

    from examples.fastapi_simple.app import app

    with TestClient(app) as client:
        assert client.get("/health").json() == {"native": True}
        assert client.post(
            "/authorize",
            json={"user": "alice", "amount": 20},
        ).json() == {"decision": "Allow", "allowed": True, "daily_limit": 50}
        assert client.post(
            "/authorize",
            json={"user": "alice", "amount": 20},
        ).json() == {"decision": "Allow", "allowed": True, "daily_limit": 50}
        assert client.post(
            "/authorize",
            json={"user": "alice", "amount": 20},
        ).json() == {"decision": "Deny", "allowed": False, "daily_limit": 50}

        assert client.post(
            "/authorize/quota",
            json={"user": "carol", "amount": 1},
        ).json() == {"decision": "Allow", "allowed": True, "hourly_quota": 2}
        assert client.post(
            "/authorize/quota",
            json={"user": "carol", "amount": 1},
        ).json() == {"decision": "Allow", "allowed": True, "hourly_quota": 2}
        assert client.post(
            "/authorize/quota",
            json={"user": "carol", "amount": 1},
        ).json() == {"decision": "Deny", "allowed": False, "hourly_quota": 2}
