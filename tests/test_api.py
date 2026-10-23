from fastapi.testclient import TestClient

from backend.app import app


def test_local_access_validation_and_state(tmp_path, monkeypatch):
    monkeypatch.setenv("RPI_LAB_HOME", str(tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/status").json()["power"] == "OFF"
        assert client.post("/api/power/on").status_code == 409
        assert client.post("/api/uart", json={"mode": "../../etc"}).status_code == 422
        assert (
            client.post(
                "/api/network",
                json={"up": False},
                headers={"Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        assert (
            client.get("/api/status", headers={"Host": "evil.example"}).status_code
            == 403
        )
        assert (
            client.post("/api/uart", json={"mode": "host"})
            .json()["uart"]["endpoint"]
            .endswith("/uart0")
        )
        assert (
            client.post("/api/uart", json={"mode": "disconnected"}).json()["uart"][
                "endpoint"
            ]
            is None
        )
        assert (
            client.post("/api/media/import", content=b"not a filesystem").status_code
            == 409
        )


def test_browser_console_access_is_disabled(tmp_path, monkeypatch):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    monkeypatch.setenv("RPI_LAB_HOME", str(tmp_path))
    with TestClient(app) as client:
        assert client.post("/api/uart", json={"mode": "browser"}).status_code == 422
        for endpoint in ("/api/serial", "/api/display"):
            with pytest.raises(WebSocketDisconnect) as denied:
                with client.websocket_connect(endpoint):
                    pass
            assert denied.value.code == 1008
