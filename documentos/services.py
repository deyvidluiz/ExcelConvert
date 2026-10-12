import hashlib
import io
from pathlib import Path

from django import forms
from django.conf import settings
from PIL import Image, UnidentifiedImageError


def _read_uploaded(uploaded):
    uploaded.seek(0)
    data = uploaded.read()
    uploaded.seek(0)
    return data


def inspect_upload(uploaded):
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if uploaded.size > max_bytes:
        raise forms.ValidationError(f"o arquivo excede o limite de {settings.MAX_UPLOAD_SIZE_MB} MB")
    data = _read_uploaded(uploaded)
    suffix = Path(uploaded.name).suffix.lower()
    mime = None
    page_count = 1
    if data.startswith(b"%PDF-") and suffix == ".pdf":
        mime = "application/pdf"
        try:
            import fitz

            page_count = len(fitz.open(stream=data, filetype="pdf"))
        except Exception as exc:
            raise forms.ValidationError("PDF inválido ou corrompido.") from exc
    elif suffix in {".jpg", ".jpeg", ".png"}:
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise forms.ValidationError("imagem inválida ou corrompida.") from exc
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"PNG", "JPEG"}:
                raise forms.ValidationError("a imagem precisa estar em PNG ou JPEG.")
            mime = "image/png" if image.format == "PNG" else "image/jpeg"
    else:
        raise forms.ValidationError("formato não suportado; envie PDF, JPG, JPEG ou PNG válido.")
    if page_count > settings.MAX_DOCUMENT_PAGES:
        raise forms.ValidationError(f"o documento excede o limite de {settings.MAX_DOCUMENT_PAGES} páginas")
    return {"mime_type": mime, "page_count": page_count, "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
