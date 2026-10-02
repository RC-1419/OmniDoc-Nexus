import os
import re
import uuid
from pathlib import Path

from omnidoc.providers.storage.base import FileStore

_KEY_RE = re.compile(r"^[0-9a-f]{32}$")  # blocks path tricks like "../"


class LocalFileStore(FileStore):
    """Plain byte storage on disk, one folder per user. Encryption is layered on top."""

    def __init__(self, root: str):
        self.root = Path(root)

    def _path(self, user_id: int, key: str) -> Path:
        if not _KEY_RE.match(key):
            raise ValueError("Invalid storage key")
        return self.root / f"user-{int(user_id)}" / f"{key}.bin"

    def save(self, user_id, data):
        key = uuid.uuid4().hex
        path = self._path(user_id, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)  # atomic: no half-written files
        return key

    def load(self, user_id, key):
        return self._path(user_id, key).read_bytes()

    def delete(self, user_id, key):
        self._path(user_id, key).unlink(missing_ok=True)
