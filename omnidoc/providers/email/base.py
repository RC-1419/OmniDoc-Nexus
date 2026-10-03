import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


class EmailError(Exception):
    """A sending failure, described without addresses, passwords or message text."""

    def __init__(self, provider: str, detail: str):
        super().__init__(f"{provider}: {detail}")
        self.provider = provider
        self.detail = detail


@dataclass
class Attachment:
    filename: str
    mime: str
    data: bytes

    def __post_init__(self):  # no path tricks or header injection through the file name
        self.filename = re.sub(
            r"[\r\n/\\]", "_", self.filename)[:100] or "document"


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    body: str
    attachment: Attachment | None = None


_ADDRESS = re.compile(r"^[^@\s<>,;\"']+@[^@\s<>,;\"']+\.[^@\s<>,;\"']+$")


def clean_address(address: str) -> str:
    address = (address or "").strip()
    if len(address) > 254 or not _ADDRESS.match(address):
        raise ValueError("That doesn't look like a valid email address")
    return address


def clean_subject(subject: str) -> str:
    return re.sub(r"[\r\n]+", " ", subject or "").strip()[:200]


class EmailProvider(ABC):
    name: str
    label: str

    @classmethod
    @abstractmethod
    def is_configured(cls) -> bool:
        """True when the settings needed to send are present."""

    @classmethod
    def can_attach(cls) -> bool:
        return True

    @abstractmethod
    def send(self, message: OutgoingEmail) -> None:
        """Send or raise EmailError."""
