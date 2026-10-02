from omnidoc.core import crypto
from omnidoc.providers.storage.base import FileStore


class EncryptedFileStore(FileStore):
    """Wraps any FileStore (local, S3...) and encrypts with the user's own key."""

    def __init__(self, inner: FileStore):
        self.inner = inner

    def save(self, user_id, data):
        return self.inner.save(user_id, crypto.encrypt_bytes(user_id, data))

    def load(self, user_id, key):
        return crypto.decrypt_bytes(user_id, self.inner.load(user_id, key))

    def delete(self, user_id, key):
        self.inner.delete(user_id, key)
