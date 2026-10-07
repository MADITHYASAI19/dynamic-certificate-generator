import pytest
import os
import shutil
from app.storage.local import LocalStorage
from app.core.config import settings

@pytest.fixture
def storage(tmp_path):
    # Use tmp_path for isolated tests
    return LocalStorage(str(tmp_path))

def test_save_and_open(storage):
    key = "jobs/123/cert.pdf"
    data = b"PDF Content"

    storage.save(key, data)
    assert storage.exists(key)
    assert storage.open(key) == data

def test_delete(storage):
    key = "jobs/123/cert.pdf"
    storage.save(key, b"data")
    assert storage.delete(key) is True
    assert not storage.exists(key)

def test_path_traversal_dot_dot(storage):
    key = "../../../etc/passwd"
    with pytest.raises(ValueError, match="Path traversal attempted"):
        storage.save(key, b"hack")

def test_path_traversal_absolute(storage):
    key = "/etc/passwd"
    with pytest.raises(ValueError, match="Path traversal attempted"):
        storage.open(key)

def test_path_traversal_resolved(storage, tmp_path):
    # Create a real file outside the base path
    outside_file = tmp_path.parent / "outside.txt"
    outside_file.write_text("secret")

    # Attempt to access it via a symlink or complex path if possible
    # LocalStorage._safe_path uses .resolve() and .is_relative_to()
    key = "some_dir/../../outside.txt"
    with pytest.raises(ValueError, match="Path traversal attempted"):
        storage.open(key)
