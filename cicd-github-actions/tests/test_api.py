import pytest

from app.main import create_app


@pytest.fixture
def client():
    application = create_app()
    application.config.update(TESTING=True)
    with application.test_client() as test_client:
        yield test_client


def test_health_reports_ok(client):
    body = client.get("/api/health").get_json()
    assert body["status"] == "ok"
    assert body["version"]


def test_index_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Task API" in response.data


def test_create_and_read_a_task(client):
    created = client.post("/api/tasks", json={"title": "ship it"})
    assert created.status_code == 201
    task_id = created.get_json()["id"]
    assert client.get("/api/tasks/%d" % task_id).get_json()["title"] == "ship it"


def test_create_rejects_an_empty_title(client):
    response = client.post("/api/tasks", json={"title": ""})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_missing_task_returns_404(client):
    assert client.get("/api/tasks/404").status_code == 404


def test_list_returns_a_summary(client):
    client.post("/api/tasks", json={"title": "one"})
    client.post("/api/tasks", json={"title": "two", "state": "done"})
    body = client.get("/api/tasks").get_json()
    assert len(body["tasks"]) == 2
    assert body["summary"]["done"] == 1
