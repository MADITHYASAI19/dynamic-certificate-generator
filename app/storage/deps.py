from fastapi import Depends
from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorage

def get_storage() -> StorageBackend:
    """
    Dependency provider for storage.
    Driven by config to allow easy swapping of backends.
    """
    # In the future, we can add a STORAGE_BACKEND env var
    # if settings.STORAGE_BACKEND == "s3":
    #     return S3Storage(...)
    return LocalStorage(settings.STORAGE_PATH)
