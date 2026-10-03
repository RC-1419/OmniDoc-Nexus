import smtplib
import ssl

from omnidoc.core.config import get_settings
from omnidoc.providers.email.base import EmailError, EmailProvider, OutgoingEmail
from omnidoc.providers.email.mime import build_mime


class SmtpProvider(EmailProvider):
    """smtplib with any SMTP server (Gmail with an app password, Outlook, Yahoo, your own)."""

    name = "smtp"
    label = "SMTP (smtplib)"

    def __init__(self, user: str | None = None, password: str | None = None):
        s = get_settings()
        self.host, self.port, self.timeout = s.smtp_host, s.smtp_port, s.email_timeout_seconds
        self.user = user or s.smtp_user
        self.password = password or s.smtp_password
        self.sender = s.smtp_from or self.user

    @classmethod
    def is_configured(cls) -> bool:
        s = get_settings()
        return bool(s.smtp_user and s.smtp_password)

    def send(self, message: OutgoingEmail) -> None:
        mime = build_mime(message, self.sender)
        context = ssl.create_default_context()
        try:
            if self.port == 465:  # implicit TLS
                with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=self.timeout) as smtp:
                    smtp.login(self.user, self.password)
                    smtp.send_message(mime)
            else:  # 587: start plain, then upgrade to TLS before the password is sent
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
                    smtp.starttls(context=context)
                    smtp.login(self.user, self.password)
                    smtp.send_message(mime)
        except smtplib.SMTPAuthenticationError:
            raise EmailError(
                self.name, "login rejected (check SMTP_USER and the app password)") from None
        except (smtplib.SMTPException, OSError) as e:
            raise EmailError(self.name, type(e).__name__) from None
