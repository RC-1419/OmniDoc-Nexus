import base64
import os

from omnidoc.core.config import get_settings
from omnidoc.providers.email.base import EmailError, EmailProvider, OutgoingEmail
from omnidoc.providers.email.mime import build_mime

# send only: it cannot read your mailbox
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailProvider(EmailProvider):
    """Gmail API with OAuth. One-time setup: python -m scripts.gmail_authorize"""

    name = "gmail"
    label = "Gmail API"

    @classmethod
    def is_configured(cls) -> bool:
        return os.path.exists(get_settings().gmail_token_path)

    def _service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        path = get_settings().gmail_token_path
        creds = Credentials.from_authorized_user_file(path, SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(path, "w") as f:
                    f.write(creds.to_json())
            else:
                raise EmailError(
                    self.name, "authorisation expired: run python -m scripts.gmail_authorize again")
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def send(self, message: OutgoingEmail) -> None:
        from google.auth.exceptions import GoogleAuthError
        from googleapiclient.errors import HttpError

        try:
            sender = get_settings().gmail_sender  # empty: Gmail uses the authorised account
            raw = base64.urlsafe_b64encode(
                build_mime(message, sender).as_bytes()).decode()
            self._service().users().messages().send(
                userId="me", body={"raw": raw}).execute()
        except EmailError:
            raise
        except HttpError as e:
            raise EmailError(
                self.name, f"HttpError (HTTP {e.resp.status})") from None
        except (GoogleAuthError, OSError) as e:
            raise EmailError(self.name, type(e).__name__) from None
