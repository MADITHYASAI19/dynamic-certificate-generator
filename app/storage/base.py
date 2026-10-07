from abc import ABC, abstractmethod
from typing import BinaryIO, Union

class StorageBackend(ABC):
    @abstractmethod
    def save(self, key: str, data: Union[bytes, BinaryIO]) -> str:
        """Saves data to storage and returns the final key/path."""
        pass

    @abstractmethod
    def open(self, key: str) -> Union[bytes, BinaryIO]:
        """Opens data from storage."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Deletes data from storage."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Checks if data exists in storage."""
        pass
