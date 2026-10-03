from omnidoc.core.config import get_settings
from omnidoc.providers.email.base import EmailError, EmailProvider, OutgoingEmail


class SendlibProvider(EmailProvider):
    """HTTP email API at SENDLIB_API_URL.

    NOT FINISHED ON PURPOSE: the request format (fields, authentication, attachment support) comes from
    the API's own documentation, which has not been supplied yet. Until it is, this provider stays
    switched off (SENDLIB_ENABLED=false) and raises a clear error if it is ever called.
    """

    name = "sendlib"
    label = "Sendlib API"

    @classmethod
    def is_configured(cls) -> bool:
        s = get_settings()
        return bool(s.sendlib_enabled and s.sendlib_api_key)

    @classmethod
    # opt-in: ID documents should not go through a service you have not vetted
    def can_attach(cls) -> bool:
        return get_settings().sendlib_allow_attachments

    def send(self, message: OutgoingEmail) -> None:
        raise EmailError(
            self.name, "request format not filled in yet (needs the API documentation)")
