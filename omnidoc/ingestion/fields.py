import re

# Verhoeff checksum tables (Aadhaar numbers carry a Verhoeff check digit)
_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
      [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1], [
          6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
      [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
      [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1], [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_valid(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_check_digit(number: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


# 12 digits (4-4-4), first digit 2-9, and NOT part of a longer digit run (e.g. a 16-digit VID)
_AADHAAR = re.compile(
    r"(?<!\d)(?<!\d[ -])([2-9]\d{3})[ -]?(\d{4})[ -]?(\d{4})(?![ -]?\d)")
_PAN = re.compile(r"\b[A-Z]{3}[ABCEFGHJKLPT][A-Z]\d{4}[A-Z]\b")
# PAN-shaped token, tolerant of spaces and OCR confusions: 5 chars, 4 chars, 1 char
_PAN_LOOSE = re.compile(
    r"(?<![A-Z0-9])([A-Z0-9]{5})\s?([A-Z0-9]{4})\s?([A-Z0-9])(?![A-Z0-9])")
# digits OCR mistakes for letters
_TO_LETTER = str.maketrans("0125684", "OIZSGBA")
# letters OCR mistakes for digits
_TO_DIGIT = str.maketrans("OQDILZSGBA", "0001125684")
_PASSPORT = re.compile(r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b")


def _find_pan(text: str) -> tuple[str | None, bool]:
    """Return (pan, exact). exact=False means OCR confusions (O/0, S/5, B/8...) had to be corrected."""
    m = _PAN.search(text)
    if m:
        return m.group(0), True
    for m in _PAN_LOOSE.finditer(text.upper()):
        a, b, c = m.groups()
        if sum(ch.isdigit() for ch in b) < 2:  # real digits needed, or ordinary words would match
            continue
        fixed = a.translate(_TO_LETTER) + \
            b.translate(_TO_DIGIT) + c.translate(_TO_LETTER)
        if _PAN.fullmatch(fixed):
            return fixed, fixed == a + b + c
    return None, False


def extract_fields(text: str) -> dict[str, str]:
    """Pull exact identifiers out of OCR/PDF text. Returned values are sensitive: never log them."""
    low = text.lower()
    fields: dict[str, str] = {}

    candidates = ["".join(m.groups()) for m in _AADHAAR.finditer(text)]
    valid = [c for c in candidates if verhoeff_valid(c)]
    if valid:
        c = valid[0]
        fields["aadhaar_number"] = f"{c[:4]} {c[4:8]} {c[8:]}"
    elif candidates and ("aadhaar" in low or "uidai" in low or "unique identification" in low):
        # checksum failed: probably an OCR misread, so flag it
        c = candidates[0]
        fields["aadhaar_number_unverified"] = f"{c[:4]} {c[4:8]} {c[8:]}"

    pan, exact = _find_pan(text)
    if pan:
        fields["pan_number" if exact else "pan_number_unverified"] = pan

    if "passport" in low:
        passport = _PASSPORT.search(text)
        if passport:
            fields["passport_number"] = passport.group(0).replace(" ", "")

    return fields


def suggest_doc_type(text: str, fields: dict[str, str]) -> str | None:
    low = text.lower()
    if "aadhaar_number" in fields or "aadhaar_number_unverified" in fields or "unique identification authority" in low:
        return "aadhaar"
    if "pan_number" in fields or "pan_number_unverified" in fields or "income tax department" in low:
        return "pan"
    if "passport_number" in fields or "passport" in low:
        return "passport"
    return None
