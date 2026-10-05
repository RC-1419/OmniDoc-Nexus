from omnidoc.ingestion.fields import _AADHAAR, _PAN, _PASSPORT


def redact_sensitive(text: str) -> str:
    """Remove ID numbers from text before it is sent to an AI provider."""
    text = _AADHAAR.sub("[aadhaar number removed]", text)
    text = _PAN.sub("[PAN removed]", text)
    return _PASSPORT.sub("[passport number removed]", text)
