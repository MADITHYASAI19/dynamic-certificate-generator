import os
from pathlib import Path
from typing import BinaryIO, Union
from app.storage.base import StorageBackend

class LocalStorage(StorageBackend):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()

    def _safe_path(self, key: str) -> Path:
        """
        Prevents path traversal by ensuring the final path is within base_path.
        """
        if ".." in key or key.startswith("/") or key.startswith("\\"):
            raise ValueError("Invalid key: Path traversal attempted.")

        final_path = (self.base_path / key).resolve()

        if not final_path.is_relative_to(self.base_path):
            raise ValueError("Invalid key: Path traversal attempted.")

        return final_path

    def save(self, key: str, data: Union[bytes, BinaryIO]) -> str:
        path = self._safe_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            with open(path, "wb") as f:
                f.write(data.read())

        return str(path)

    def open(self, key: str) -> Union[bytes, BinaryIO]:
        path = self._safe_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Key {key} not found")
        return path.read_bytes()

    def delete(self, key: str) -> bool:
        path = self._safe_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        path = self._safe_path(key)
        return path.exists()
