import re

# A person has at most one of each of these; uploading again replaces the old one.
UNIQUE_TYPES = {"aadhaar", "pan", "passport", "voter_id", "driving_licence"}

_ALIASES = {
    "aadhar": "aadhaar", "aadhaar_card": "aadhaar", "aadhar_card": "aadhaar", "uid": "aadhaar", "uidai": "aadhaar",
    "pan_card": "pan", "permanent_account_number": "pan",
    "driving_license": "driving_licence", "driver_license": "driving_licence", "dl": "driving_licence",
    "license": "driving_licence", "licence": "driving_licence",
    "voter": "voter_id", "voter_card": "voter_id", "voter_id_card": "voter_id", "epic": "voter_id",
}


def normalize_doc_type(value: str | None) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")[:60]
    return _ALIASES.get(slug, slug) or "other"
