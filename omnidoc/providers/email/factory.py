from dataclasses import dataclass
from functools import lru_cache

from omnidoc.core.config import get_settings
from omnidoc.providers.email.base import EmailError, EmailProvider, OutgoingEmail
from omnidoc.providers.email.gmail_provider import GmailProvider
from omnidoc.providers.email.sendlib_provider import SendlibProvider
from omnidoc.providers.email.smtp_provider import SmtpProvider

PROVIDERS: dict[str, type[EmailProvider]] = {
    "smtp": SmtpProvider, "gmail": GmailProvider, "sendlib": SendlibProvider}


def configured_email_providers() -> list[str]:
    return [name for name, cls in PROVIDERS.items() if cls.is_configured()]


@lru_cache
def get_email_provider(name: str) -> EmailProvider:
    return PROVIDERS[name]()


def provider_order(preferred: str | None, needs_attachment: bool) -> list[str]:
    """The chosen provider first, then the rest of EMAIL_PROVIDER_ORDER. Only providers that are set up
    and (for attachments) allowed to carry them."""
    wanted = [preferred] if preferred else []
    wanted += [n.strip()
               for n in get_settings().email_provider_order.split(",")]
    order = []
    for name in wanted:
        cls = PROVIDERS.get(name)
        if cls and name not in order and cls.is_configured() and (cls.can_attach() or not needs_attachment):
            order.append(name)
    return order


@dataclass
class SendResult:
    provider: str
    failed: list[str]  # providers tried before this one, with the reason


def send_with_fallback(providers: list[EmailProvider], message: OutgoingEmail) -> SendResult:
    failed = []
    for provider in providers:
        try:
            provider.send(message)
            return SendResult(provider.name, failed)
        except EmailError as e:
            failed.append(str(e))
    raise EmailError("all providers", "; ".join(
        failed) or "no email provider is set up")
