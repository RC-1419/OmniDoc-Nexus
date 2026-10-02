import io
import re
import sys

import pytesseract
from PIL import Image, ImageFilter, ImageOps

from omnidoc.core.config import get_settings
from omnidoc.ingestion.fields import extract_fields

s = get_settings()
if s.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = s.tesseract_cmd

KEYWORDS = ("income", "tax", "department", "permanent", "account", "number", "govt", "india", "signature", "father")


def load(path):
    data = open(path, "rb").read()
    if data.startswith(b"%PDF"):
        import pypdfium2 as pdfium
        from pypdf import PdfReader
        try:
            return PdfReader(io.BytesIO(data)).pages[0].images[0].image
        except Exception:
            return pdfium.PdfDocument(data)[0].render(scale=3).to_pil()
    return Image.open(io.BytesIO(data))


def otsu(img):
    hist = img.histogram()[:256]
    total, sum_all = sum(hist), sum(i * h for i, h in enumerate(hist))
    best, thr, w0, sum0 = 0, 128, 0, 0
    for t in range(256):
        w0 += hist[t]
        if w0 == 0:
            continue
        w1 = total - w0
        if w1 == 0:
            break
        sum0 += t * hist[t]
        var = w0 * w1 * (sum0 / w0 - (sum_all - sum0) / w1) ** 2
        if var > best:
            best, thr = var, t
    return img.point(lambda p: 255 if p > thr else 0)


def prepare(img, channel, size, prep):
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = img.convert("L") if channel == "gray" else img.getchannel(channel)
    img = ImageOps.autocontrast(img)
    r = size / max(img.size)
    img = img.resize((int(img.width * r), int(img.height * r)), Image.LANCZOS)
    if prep == "sharp":
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    elif prep == "bw":
        img = otsu(img)
    return img


def run(img, channel, size, prep, psm, rot=0):
    text = pytesseract.image_to_string(prepare(img.rotate(rot, expand=True), channel, size, prep),
                                       lang=s.ocr_languages, config=f"--psm {psm}")
    low = text.lower()
    fields = extract_fields(text)
    has_pan = any(k.startswith("pan_number") for k in fields)
    return (has_pan, sum(k in low for k in KEYWORDS), len(re.findall(r"\d", text)), ",".join(fields) or "-")


img = load(sys.argv[1])
print("image size:", img.size, "| mode:", img.mode)

print("\n-- orientation (2000px, psm 11) --")
orient = []
for rot in (0, 90, 180, 270):
    for channel in ("gray", "B"):
        res = run(img, channel, 2000, "plain", 11, rot)
        orient.append((res[:3], rot))
        print(f"rotation {rot} {channel}: keywords={res[1]} digits={res[2]} fields={res[3]}")
best_rot = max(orient, key=lambda o: (o[0], -o[1]))[1]
print("using rotation", best_rot)

rows = []
print("\n-- stage 1: channel x size --")
for channel in ("gray", "B", "R"):
    for size in (2500, 3500, 4500):
        res = run(img, channel, size, "plain", 11, best_rot)
        rows.append((*res, channel, size, "plain", 11))
        print(f"{channel} {size}px: keywords={res[1]} digits={res[2]} fields={res[3]}")

b = max(rows, key=lambda r: r[:3])
print(f"\n-- stage 2: preparation x layout mode, on best ({b[4]}, {b[5]}px) --")
for prep in ("plain", "sharp", "bw"):
    for psm in (6, 11, 12):
        res = run(img, b[4], b[5], prep, psm, best_rot)
        rows.append((*res, b[4], b[5], prep, psm))

rows.sort(key=lambda r: r[:3], reverse=True)
print("\n-- best overall --\nPAN found | keywords | digits | fields | channel | size | prep | psm")
for r in rows[:8]:
    print(*r, sep=" | ")