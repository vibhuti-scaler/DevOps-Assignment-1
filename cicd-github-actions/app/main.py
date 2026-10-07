"""HTTP layer for the Task API used by the CI/CD pipeline."""
import os

from flask import Flask, jsonify, render_template, request

from app.tasks import TaskError, TaskStore

APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")
APP_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", "development")


def create_app(store=None):
    app = Flask(__name__)
    app.config["STORE"] = store or TaskStore()

    @app.get("/")
    def index():
        store = app.config["STORE"]
        return render_template("index.html", version=APP_VERSION,
                               environment=APP_ENVIRONMENT, tasks=store.list(),
                               summary=store.summary())

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", version=APP_VERSION, environment=APP_ENVIRONMENT)

    @app.get("/api/tasks")
    def list_tasks():
        store = app.config["STORE"]
        return jsonify(tasks=store.list(), summary=store.summary())

    @app.post("/api/tasks")
    def create_task():
        store = app.config["STORE"]
        payload = request.get_json(silent=True) or {}
        try:
            task = store.add(payload.get("title"), payload.get("state", "todo"))
        except TaskError as error:
            return jsonify(error=str(error)), 400
        return jsonify(task), 201

    @app.get("/api/tasks/<int:task_id>")
    def read_task(task_id):
        task = app.config["STORE"].get(task_id)
        if task is None:
            return jsonify(error="task not found"), 404
        return jsonify(task)

    return app


app = create_app()

if __name__ == "__main__":  # pragma: no cover - entrypoint, exercised by Docker
    # Loopback by default. This path is the development server only; the
    # container runs gunicorn, which binds 0.0.0.0 from its own command line.
    # Binding every interface here was flagged by Bandit as B104 and there is
    # no reason for a debug entrypoint to be reachable off the machine.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
