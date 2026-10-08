# One image runs both the API and the Streamlit app; docker-compose picks the command.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# tesseract = text reading for scans; poppler is not needed (PDF pages are read with pypdf/Pillow)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY omnidoc ./omnidoc
COPY scripts ./scripts

# Run as a normal user, not root. /data holds the encrypted vault (mounted as a volume).
RUN useradd --create-home --uid 1000 omnidoc && mkdir -p /data/vault && chown -R omnidoc /data /app
USER omnidoc

EXPOSE 8000 8501
CMD ["uvicorn", "omnidoc.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
