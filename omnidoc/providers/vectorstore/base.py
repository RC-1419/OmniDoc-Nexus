from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VectorItem:
    id: str
    vector: list[float]
    metadata: dict = field(default_factory=dict)


@dataclass
class Match:
    id: str
    score: float
    metadata: dict = field(default_factory=dict)


class VectorStore(ABC):
    """Every method takes user_id. A store can never be used without saying whose data it is."""

    @abstractmethod
    def upsert(self, user_id: int, items: list[VectorItem]) -> None: ...

    @abstractmethod
    def query(self, user_id: int, vector: list[float], top_k: int = 5,
              filters: dict | None = None) -> list[Match]: ...

    @abstractmethod
    def delete(self, user_id: int, ids: list[str]) -> None:
        """Callers pass only ids taken from that user's own rows in Postgres."""
