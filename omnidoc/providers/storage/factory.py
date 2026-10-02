from functools import lru_cache

from omnidoc.core.config import get_settings
from omnidoc.providers.storage.base import FileStore
from omnidoc.providers.storage.encrypted import EncryptedFileStore
from omnidoc.providers.storage.local import LocalFileStore


@lru_cache
def get_file_store() -> FileStore:
    return EncryptedFileStore(LocalFileStore(get_settings().vault_dir))
