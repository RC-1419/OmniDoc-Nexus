from abc import ABC, abstractmethod


class Embedder(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Vectors for passages that will be stored."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Vector for a user's question."""
