import tempfile

import pytest

from app.storage.object_store import LocalObjectStore, ObjectStore


@pytest.fixture
def local_store():
    """Create a temporary local object store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalObjectStore(base_dir=tmpdir)
        yield store


def test_upload_and_download(local_store: ObjectStore):
    """Test basic upload and download operations."""
    key = "test/file.txt"
    data = b"Hello, world!"

    result = local_store.upload(key, data, content_type="text/plain")
    assert result == key

    downloaded = local_store.download(key)
    assert downloaded == data


def test_exists(local_store: ObjectStore):
    """Test exists check."""
    key = "test/exists.txt"
    assert not local_store.exists(key)

    local_store.upload(key, b"content")
    assert local_store.exists(key)


def test_delete(local_store: ObjectStore):
    """Test delete operation."""
    key = "test/delete.txt"
    local_store.upload(key, b"to delete")
    assert local_store.exists(key)

    local_store.delete(key)
    assert not local_store.exists(key)


def test_delete_nonexistent(local_store: ObjectStore):
    """Test deleting a non-existent key doesn't raise error."""
    local_store.delete("nonexistent/file.txt")  # Should not raise


def test_upload_nested_path(local_store: ObjectStore):
    """Test uploading to nested paths creates directories automatically."""
    key = "deep/nested/path/file.txt"
    data = b"nested content"

    local_store.upload(key, data)
    downloaded = local_store.download(key)
    assert downloaded == data
