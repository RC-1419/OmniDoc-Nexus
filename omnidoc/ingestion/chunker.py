def chunk_text(text: str, size: int = 600, overlap: int = 80) -> list[str]:
    """Split text into overlapping windows so a fact cut at a boundary still appears whole in one chunk."""
    text = " ".join(text.split())
    if not text:
        return []
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step)]
