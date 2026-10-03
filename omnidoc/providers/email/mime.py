from email.message import EmailMessage as MimeMessage

from omnidoc.providers.email.base import OutgoingEmail


def build_mime(message: OutgoingEmail, sender: str) -> MimeMessage:
    """Shared by every provider that sends a standard MIME message (SMTP, Gmail API)."""
    mime = MimeMessage()
    if sender:  # left out for Gmail's API, which fills in the authorised account itself
        mime["From"] = sender
    mime["To"], mime["Subject"] = message.to, message.subject
    mime.set_content(message.body)
    a = message.attachment
    if a:
        maintype, _, subtype = a.mime.partition("/")
        mime.add_attachment(a.data, maintype=maintype or "application",
                            subtype=subtype or "octet-stream", filename=a.filename)
    return mime
