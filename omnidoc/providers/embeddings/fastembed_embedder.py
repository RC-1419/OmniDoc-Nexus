from functools import cached_property

from omnidoc.providers.embeddings.base import Embedder


class FastEmbedder(Embedder):
    """Runs a small model locally (ONNX): free, no API key, text never leaves your machine."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    @cached_property
    def _model(self):  # loaded on first use; the first run downloads the model once
        from fastembed import TextEmbedding

        from omnidoc.core.config import get_settings

        return TextEmbedding(model_name=self.model_name, cache_dir=get_settings().embedding_cache_dir)

    def embed_documents(self, texts):
        return [v.tolist() for v in self._model.passage_embed(texts)]

    def embed_query(self, text):
        return next(iter(self._model.query_embed(text))).tolist()
