import io
import re

from omnidoc.core.config import get_settings
from omnidoc.ingestion.fields import extract_fields


class UnsupportedFileType(ValueError):
    pass


class FileTooLarge(ValueError):
    pass


def detect_mime(data: bytes) -> str:
    """Decide the type from the file's own bytes; never trust the browser's content-type."""
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise UnsupportedFileType("Only PDF, PNG and JPG files are supported")


_KEYWORDS = ("income", "tax", "department", "permanent", "account", "number", "govt", "india", "government",
             "aadhaar", "unique", "identification", "authority", "birth", "father", "signature", "passport")


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z]{3,}", text))


def _score(text: str) -> tuple:
    """How much this OCR result looks like a real ID: verified fields, any fields, keywords, digits."""
    low = text.lower()
    fields = extract_fields(text)
    verified = sum(1 for k in fields if not k.endswith("_unverified"))
    return (verified, len(fields), sum(k in low for k in _KEYWORDS), len(re.findall(r"\d", text)))


def _ocr_once(img) -> str:
    import pytesseract

    s = get_settings()
    if s.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = s.tesseract_cmd
    return pytesseract.image_to_string(img, lang=s.ocr_languages, config=f"--psm {s.ocr_psm}")


def _prepare(img, channel: str):
    """One colour channel often reads far better than greyscale (e.g. the blue channel on PAN cards,
    where the coloured background pattern washes out in plain grey)."""
    from PIL import ImageOps

    img = ImageOps.exif_transpose(img).convert("RGB")
    img = img.convert("L") if channel.lower(
    ) == "gray" else img.getchannel(channel.upper())
    img = ImageOps.autocontrast(img)
    longest = max(img.size)
    if longest < 1500 or longest > 2500:  # keep the size in a range OCR handles well
        scale = (1500 if longest < 1500 else 2500) / longest
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    return img


def _ocr_variant(img) -> str:
    """Upright and upside-down (sideways only if those read almost nothing); keep orientations with real words."""
    texts = [_ocr_once(img.rotate(rot, expand=True)) for rot in (0, 180)]
    if sum(_words(t) for t in texts) < 10:
        texts += [_ocr_once(img.rotate(rot, expand=True)) for rot in (90, 270)]
    good = [t for t in texts if _words(t) >= 5]
    return "\n".join(good) if good else max(texts, key=len)


def _ocr_image(img) -> str:
    """Try each configured colour channel, stop as soon as a verified ID field is found, else keep the best."""
    channels = [c.strip() for c in get_settings(
    ).ocr_channels.split(",") if c.strip()] or ["gray"]
    best_text, best_score = "", None
    for channel in channels:
        text = _ocr_variant(_prepare(img, channel))
        score = _score(text)
        if best_score is None or score > best_score:
            best_text, best_score = text, score
        if score[0] > 0:  # a verified field was found: no need to try more
            break
    return best_text


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise UnsupportedFileType(
            "Password-protected PDFs are not supported yet")
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _pdf_ocr(data: bytes) -> str:
    """Scanned/photo PDFs: OCR the original embedded photo (sharper than a re-render of the page);
    fall back to rendering the page if the photo can't be extracted."""
    import pypdfium2 as pdfium
    from pypdf import PdfReader

    max_pages = get_settings().ocr_max_pages
    reader = PdfReader(io.BytesIO(data))
    pdf = pdfium.PdfDocument(data)
    parts = []
    for i in range(min(len(pdf), max_pages)):
        images = []
        try:
            images = [im.image for im in reader.pages[i].images[:3]
                      if min(im.image.size) >= 200]
        except Exception:
            pass
        if not images:
            images = [pdf[i].render(scale=3).to_pil()]
        parts += [_ocr_image(im) for im in images]
    return "\n".join(parts)


def extract_text(data: bytes, mime: str) -> str:
    if mime == "application/pdf":
        text = _pdf_text(data)
        if len(text.strip()) < 30:  # no real text layer, so OCR it
            text = _pdf_ocr(data)
        return text
    from PIL import Image

    return _ocr_image(Image.open(io.BytesIO(data)))
