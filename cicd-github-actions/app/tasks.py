"""Task storage and the rules around it.

The logic is deliberately kept out of the HTTP layer so it can be unit tested
without starting a server, which is what keeps the CI test job fast.
"""


class TaskError(ValueError):
    """Raised when a caller sends a task the store will not accept."""


class TaskStore:
    MAX_TITLE = 80
    VALID_STATES = ("todo", "doing", "done")

    def __init__(self):
        self._tasks = {}
        self._next_id = 1

    def add(self, title, state="todo"):
        title = (title or "").strip()
        if not title:
            raise TaskError("title must not be empty")
        if len(title) > self.MAX_TITLE:
            raise TaskError("title must be at most %d characters" % self.MAX_TITLE)
        if state not in self.VALID_STATES:
            raise TaskError("state must be one of %s" % ", ".join(self.VALID_STATES))
        task = {"id": self._next_id, "title": title, "state": state}
        self._tasks[self._next_id] = task
        self._next_id += 1
        return task

    def get(self, task_id):
        return self._tasks.get(task_id)

    def list(self):
        return [self._tasks[key] for key in sorted(self._tasks)]

    def set_state(self, task_id, state):
        if state not in self.VALID_STATES:
            raise TaskError("state must be one of %s" % ", ".join(self.VALID_STATES))
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task["state"] = state
        return task

    def summary(self):
        counts = {state: 0 for state in self.VALID_STATES}
        for task in self._tasks.values():
            counts[task["state"]] += 1
        return counts
