import pytest

from notes.store import NoteStore, StoreError


@pytest.fixture
def store(tmp_path):
    return NoteStore(str(tmp_path / "notes.json"))


def test_ids_increment(store):
    assert store.add("first")["id"] == 1
    assert store.add("second")["id"] == 2


def test_titles_are_trimmed(store):
    assert store.add("  spaced  ")["title"] == "spaced"


@pytest.mark.parametrize("title", ["", "   ", None])
def test_empty_titles_are_rejected(store, title):
    with pytest.raises(StoreError):
        store.add(title)


def test_long_title_is_rejected(store):
    with pytest.raises(StoreError):
        store.add("x" * 121)


def test_long_body_is_rejected(store):
    with pytest.raises(StoreError):
        store.add("ok", "y" * 2001)


def test_notes_survive_a_new_store_object(tmp_path):
    path = str(tmp_path / "notes.json")
    NoteStore(path).add("persisted")
    assert [note["title"] for note in NoteStore(path).list()] == ["persisted"]


def test_delete_removes_only_the_requested_note(store):
    first = store.add("one")
    store.add("two")
    assert store.delete(first["id"]) is True
    assert [note["title"] for note in store.list()] == ["two"]


def test_delete_reports_a_missing_note(store):
    assert store.delete(99) is False


def test_a_corrupt_file_does_not_raise(tmp_path):
    path = tmp_path / "notes.json"
    path.write_text("{ not json")
    assert NoteStore(str(path)).list() == []


def test_writable_reports_true_for_a_healthy_volume(store):
    assert store.writable() is True
