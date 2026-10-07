import pytest

from notes.app import create_app
from notes.store import NoteStore


@pytest.fixture
def client(tmp_path):
    application = create_app(NoteStore(str(tmp_path / "notes.json")))
    application.config.update(TESTING=True)
    with application.test_client() as test_client:
        yield test_client


def test_healthz(client):
    assert client.get("/healthz").get_json()["status"] == "ok"


def test_readyz_is_ready_when_storage_works(client):
    assert client.get("/readyz").get_json()["status"] == "ready"


def test_metrics_are_exposed_in_prometheus_format(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"notes_stored_total" in response.data
    assert b"notes_storage_writable" in response.data


def test_index_renders(client):
    assert b"Notes" in client.get("/").data


def test_create_then_read(client):
    created = client.post("/api/notes", json={"title": "deploy", "body": "to kubernetes"})
    assert created.status_code == 201
    note_id = created.get_json()["id"]
    assert client.get("/api/notes/%d" % note_id).get_json()["body"] == "to kubernetes"


def test_create_rejects_an_empty_title(client):
    assert client.post("/api/notes", json={"title": ""}).status_code == 400


def test_missing_note_is_404(client):
    assert client.get("/api/notes/77").status_code == 404


def test_delete_returns_no_content(client):
    note_id = client.post("/api/notes", json={"title": "temp"}).get_json()["id"]
    assert client.delete("/api/notes/%d" % note_id).status_code == 204
    assert client.get("/api/notes/%d" % note_id).status_code == 404


def test_metrics_count_the_stored_notes(client):
    client.post("/api/notes", json={"title": "counted"})
    assert b"notes_stored_total 1.0" in client.get("/metrics").data
