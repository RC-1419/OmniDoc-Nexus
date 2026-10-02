import io
import sys

import pypdfium2 as pdfium
from pypdf import PdfReader

from omnidoc.ingestion.extract import _ocr_image, _pdf_text, _score

data = open(sys.argv[1], "rb").read()
reader = PdfReader(io.BytesIO(data))
print("pages:", len(reader.pages), "| encrypted:", reader.is_encrypted)

chars = len(_pdf_text(data).strip())
print("text-layer chars:", chars, "->", "OCR would be SKIPPED (30 or more)" if chars >= 30 else "OCR will run")


def describe(label, img):
    verified, fields, keywords, digits = _score(_ocr_image(img))
    print(f"{label}: size={img.size} mode={img.mode} | verified fields={verified} any fields={fields} "
          f"keywords={keywords} digits={digits}")


pdf = pdfium.PdfDocument(data)
for i, page in enumerate(reader.pages[:3]):
    images = page.images
    print(f"\npage {i + 1}: {len(images)} embedded image(s)")
    for j, im in enumerate(images[:3]):
        try:
            describe(f"  embedded #{j + 1}", im.image)
        except Exception as e:
            print(f"  embedded #{j + 1}: cannot be read ({type(e).__name__})")
    describe("  page render (3x)", pdf[i].render(scale=3).to_pil())