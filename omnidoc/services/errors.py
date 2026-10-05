class DocumentError(Exception):
    """Base class for problems the caller can explain to the user."""


class NotFound(DocumentError):
    """Also raised when the item exists but belongs to someone else: the caller must not be able to tell."""


class QuotaExceeded(DocumentError):
    pass
