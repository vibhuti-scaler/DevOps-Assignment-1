"""Notes service: the application carried through the whole delivery chain."""
import os
import time

from flask import Flask, Response, jsonify, render_template, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from notes.store import NoteStore, StoreError

APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", "development")
DATA_PATH = os.environ.get("NOTES_DATA_PATH", "/data/notes.json")
# Read from a mounted Secret, never from the image or the manifest body.
API_TOKEN = os.environ.get("API_TOKEN", "")

REQUESTS = Counter("notes_http_requests_total", "HTTP requests handled",
                   ["method", "endpoint", "status"])
LATENCY = Histogram("notes_http_request_duration_seconds", "Request duration",
                    ["endpoint"])
NOTES_TOTAL = Gauge("notes_stored_total", "Notes currently stored")
STORAGE_WRITABLE = Gauge("notes_storage_writable", "1 when the data volume accepts writes")


def create_app(store=None):
    app = Flask(__name__)
    app.config["STORE"] = store or NoteStore(DATA_PATH)

    @app.before_request
    def _start_timer():
        request.started_at = time.perf_counter()

    @app.after_request
    def _record(response):
        endpoint = request.endpoint or "unknown"
        REQUESTS.labels(request.method, endpoint, response.status_code).inc()
        started = getattr(request, "started_at", None)
        if started is not None:
            LATENCY.labels(endpoint).observe(time.perf_counter() - started)
        return response

    def authorised():
        # No token configured means the service is open, which is the right
        # default for a local run and is overridden in every deployed one.
        if not API_TOKEN:
            return True
        return request.headers.get("X-API-Token") == API_TOKEN

    @app.get("/")
    def index():
        store = app.config["STORE"]
        return render_template("index.html", notes=store.list(), version=APP_VERSION,
                               environment=APP_ENVIRONMENT)

    @app.get("/healthz")
    def healthz():
        """Liveness: the process is running and able to answer."""
        return jsonify(status="ok", version=APP_VERSION)

    @app.get("/readyz")
    def readyz():
        """Readiness: this replica can actually serve writes."""
        writable = app.config["STORE"].writable()
        STORAGE_WRITABLE.set(1 if writable else 0)
        if not writable:
            return jsonify(status="unready", reason="data volume is not writable"), 503
        return jsonify(status="ready", environment=APP_ENVIRONMENT)

    @app.get("/metrics")
    def metrics():
        store = app.config["STORE"]
        NOTES_TOTAL.set(len(store.list()))
        STORAGE_WRITABLE.set(1 if store.writable() else 0)
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.get("/api/notes")
    def list_notes():
        return jsonify(notes=app.config["STORE"].list())

    @app.post("/api/notes")
    def create_note():
        if not authorised():
            return jsonify(error="unauthorised"), 401
        payload = request.get_json(silent=True) or {}
        try:
            note = app.config["STORE"].add(payload.get("title"), payload.get("body", ""))
        except StoreError as error:
            return jsonify(error=str(error)), 400
        return jsonify(note), 201

    @app.get("/api/notes/<int:note_id>")
    def read_note(note_id):
        note = app.config["STORE"].get(note_id)
        if note is None:
            return jsonify(error="note not found"), 404
        return jsonify(note)

    @app.delete("/api/notes/<int:note_id>")
    def delete_note(note_id):
        if not authorised():
            return jsonify(error="unauthorised"), 401
        if not app.config["STORE"].delete(note_id):
            return jsonify(error="note not found"), 404
        return "", 204

    return app


app = create_app()

if __name__ == "__main__":  # pragma: no cover - entrypoint, exercised by Docker
    # Loopback by default. This path is the development server only; the
    # container runs gunicorn, which binds 0.0.0.0 from its own command line.
    # Binding every interface here was flagged by Bandit as B104 and there is
    # no reason for a debug entrypoint to be reachable off the machine.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
