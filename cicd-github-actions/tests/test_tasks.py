import pytest

from app.tasks import TaskError, TaskStore


def test_add_assigns_incrementing_ids():
    store = TaskStore()
    assert store.add("write the CI pipeline")["id"] == 1
    assert store.add("push the image")["id"] == 2


def test_add_trims_whitespace():
    assert TaskStore().add("  tidy up  ")["title"] == "tidy up"


@pytest.mark.parametrize("title", ["", "   ", None])
def test_empty_titles_are_rejected(title):
    with pytest.raises(TaskError):
        TaskStore().add(title)


def test_long_titles_are_rejected():
    with pytest.raises(TaskError):
        TaskStore().add("x" * 81)


def test_unknown_state_is_rejected():
    with pytest.raises(TaskError):
        TaskStore().add("valid title", state="archived")


def test_set_state_updates_an_existing_task():
    store = TaskStore()
    task = store.add("review the PR")
    assert store.set_state(task["id"], "done")["state"] == "done"


def test_set_state_returns_none_for_a_missing_task():
    assert TaskStore().set_state(99, "done") is None


def test_summary_counts_every_state():
    store = TaskStore()
    store.add("a")
    store.add("b", state="doing")
    store.add("c", state="done")
    assert store.summary() == {"todo": 1, "doing": 1, "done": 1}
