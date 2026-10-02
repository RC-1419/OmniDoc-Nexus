import sys

from omnidoc.ingestion.chunker import chunk_text
from omnidoc.ingestion.fields import extract_fields, suggest_doc_type, verhoeff_check_digit, verhoeff_valid


def mask(v: str) -> str:
    return "X" * (len(v) - 4) + v[-4:]


# --- Part A: no files needed ---
assert verhoeff_valid("2363") and verhoeff_valid("123451")
base = "23456789012"
aadhaar = base + verhoeff_check_digit(base)
assert verhoeff_valid(aadhaar)
a = f"{aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}"

f = extract_fields(f"Government of India Aadhaar {a} VID 9999 8888 7777 6666")
# real number found, 16-digit VID ignored
assert f == {"aadhaar_number": a}, f
# long digit run is not an Aadhaar
assert extract_fields("Ref 1234 5678 9012 3456") == {}
bad = a[:-1] + str((int(a[-1]) + 1) % 10)
assert "aadhaar_number_unverified" in extract_fields(f"Aadhaar card {bad}")
assert extract_fields("Permanent Account Number ABCPE1234F")[
    "pan_number"] == "ABCPE1234F"
assert suggest_doc_type("Income Tax Department", {}) == "pan"
assert chunk_text("x" * 1000) and len(chunk_text("x" * 1000)
                                      [0]) == 600 and chunk_text("  ") == []
print("Part A OK: field extraction, checksum and chunking")

# --- Part B: a real file (optional) ---
if len(sys.argv) > 1:
    from omnidoc.ingestion.pipeline import process_document

    with open(sys.argv[1], "rb") as fh:
        doc = process_document(fh.read())
    print("type:", doc.mime, "| chunks:", len(
        doc.chunks), "| has_text:", doc.has_text)
    print("suggested document type:", doc.suggested_type)
    for k, v in doc.fields.items():
        print(f"  {k}: {mask(v.replace(' ', ''))}")
