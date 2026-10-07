"""Note storage, persisted as one JSON document on a mounted volume.

Keeping the file handling here means the HTTP layer never touches the disk
directly, and the storage behaviour can be tested without a running server.
"""
import json
import os
import tempfile
import threading


class StoreError(ValueError):
    """Raised when a caller sends a note the store will not accept."""


class NoteStore:
    MAX_TITLE = 120
    MAX_BODY = 2000

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)
        if not os.path.exists(path):
            self._write({"next_id": 1, "notes": []})

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            # A truncated file must not take the whole service down; the
            # readiness probe is what reports that storage is unhealthy.
            return {"next_id": 1, "notes": []}

    def _write(self, data):
        # Write to a temporary file in the same directory and rename it, so a
        # crash mid-write can never leave a half-written document behind.
        directory = os.path.dirname(self.path) or "."
        handle = tempfile.NamedTemporaryFile("w", dir=directory, delete=False,
                                             encoding="utf-8")
        try:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        os.replace(handle.name, self.path)

    def add(self, title, body=""):
        title = (title or "").strip()
        body = (body or "").strip()
        if not title:
            raise StoreError("title must not be empty")
        if len(title) > self.MAX_TITLE:
            raise StoreError("title must be at most %d characters" % self.MAX_TITLE)
        if len(body) > self.MAX_BODY:
            raise StoreError("body must be at most %d characters" % self.MAX_BODY)
        with self._lock:
            data = self._read()
            note = {"id": data["next_id"], "title": title, "body": body}
            data["notes"].append(note)
            data["next_id"] += 1
            self._write(data)
        return note

    def list(self):
        return self._read()["notes"]

    def get(self, note_id):
        for note in self._read()["notes"]:
            if note["id"] == note_id:
                return note
        return None

    def delete(self, note_id):
        with self._lock:
            data = self._read()
            remaining = [n for n in data["notes"] if n["id"] != note_id]
            if len(remaining) == len(data["notes"]):
                return False
            data["notes"] = remaining
            self._write(data)
        return True

    def writable(self):
        """Used by the readiness probe: can this replica actually serve writes?"""
        probe = self.path + ".probe"
        try:
            with open(probe, "w", encoding="utf-8") as handle:
                handle.write("ok")
            os.remove(probe)
            return True
        except OSError:
            return False
