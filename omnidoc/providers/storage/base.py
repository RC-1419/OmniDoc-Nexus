from abc import ABC, abstractmethod


class FileStore(ABC):
    """Every call takes user_id, so a store can never be used without saying whose data it is."""

    @abstractmethod
    def save(self, user_id: int, data: bytes) -> str:
        """Store data and return an opaque key."""

    @abstractmethod
    def load(self, user_id: int, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, user_id: int, key: str) -> None: ...
