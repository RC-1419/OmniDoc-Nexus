import argparse

from omnidoc.providers.email.base import Attachment, EmailError, OutgoingEmail
from omnidoc.providers.email.factory import (PROVIDERS, configured_email_providers, get_email_provider,
                                             send_with_fallback)
from omnidoc.providers.email.smtp_provider import SmtpProvider

ap = argparse.ArgumentParser()
ap.add_argument("--to", required=True, help="an address you own")
ap.add_argument("--provider", choices=list(PROVIDERS))
args = ap.parse_args()

names = [args.provider] if args.provider else configured_email_providers()
if not names:
    raise SystemExit(
        "No email provider is set up. Fill in SMTP_USER / SMTP_PASSWORD in .env first.")
print("providers to test:", ", ".join(names))

for name in names:
    provider = get_email_provider(name)
    print(f"\n== {provider.label} ==")
    try:
        provider.send(OutgoingEmail(
            args.to, "Omnidoc Nexus test: plain", "This is a test message."))
        print("plain email:      sent")
    except EmailError as e:
        print("plain email:      FAILED:", e)
    if provider.can_attach():
        try:
            provider.send(OutgoingEmail(args.to, "Omnidoc Nexus test: attachment", "Test with a fake attachment.",
                                        Attachment("test.txt", "text/plain", b"fake attachment, not a real document")))
            print("with attachment:  sent")
        except EmailError as e:
            print("with attachment:  FAILED:", e)
    else:
        print(
            "with attachment:  skipped (this provider is not allowed to carry attachments)")

if "smtp" in names:
    print("\n== fallback ==")
    result = send_with_fallback([SmtpProvider(password="wrong-password"), get_email_provider("smtp")],
                                OutgoingEmail(args.to, "Omnidoc Nexus test: fallback", "Sent after a failed first attempt."))
    print(
        f"wrong password first, then the real one: sent by {result.provider}; failed first: {result.failed}")
