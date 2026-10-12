"""Preflight seguro para testar uma página de ficha sem chamar a IA."""

import json
import math
from pathlib import Path

from django.conf import settings

from extracao.preprocessamento import preprocess_image


def render_pdf_page(pdf_path, page_number, *, dpi=180):
    """Renderiza uma página 1-based para PNG, mantendo o PDF intacto."""
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - dependência obrigatória em produção
            raise RuntimeError("PyMuPDF não está instalado; não foi possível renderizar a página.") from exc

    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF não encontrado: {path}")
    with fitz.open(path) as document:
        if page_number < 1 or page_number > len(document):
            raise ValueError(f"A página deve estar entre 1 e {len(document)}.")
        page = document.load_page(page_number - 1)
        scale = dpi / 72
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("png"), {"width": pixmap.width, "height": pixmap.height, "page_count": len(document)}


def estimate_page_usage(image_data, *, field_count):
    """Calcula uma estimativa local identificada como heurística, nunca como saldo/quota."""
    # A API não foi chamada: a estimativa serve apenas para a confirmação prévia.
    image_bytes = max(1, len(image_data))
    input_tokens = max(256, math.ceil(image_bytes / 3))
    output_tokens = max(64, field_count * 12)
    total = input_tokens + output_tokens
    cost_usd = (total / 1_000_000) * 0.10
    return {
        "kind": "heuristic_preflight",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "estimated_cost_usd": round(cost_usd, 8),
        "estimated_cost_brl": round(cost_usd * float(settings.USD_TO_BRL), 6),
        "note": "Estimativa local; não representa quota, saldo ou consumo real da conta Google.",
    }


def draw_region_overlay(image_data, fields):
    """Gera um PNG para revisão visual, desenhando somente regiões já calibradas."""
    from io import BytesIO

    from PIL import Image, ImageDraw

    image = Image.open(BytesIO(image_data)).convert("RGB")
    draw = ImageDraw.Draw(image)
    calibrated = 0
    for field in fields:
        region = field.region
        if not region:
            continue
        x = int(float(region["x"]) * image.width)
        y = int(float(region["y"]) * image.height)
        right = int((float(region["x"]) + float(region["width"])) * image.width)
        bottom = int((float(region["y"]) + float(region["height"])) * image.height)
        draw.rectangle((x, y, right, bottom), outline="#D64A4A", width=3)
        draw.text((x + 4, y + 4), field.field_id, fill="#D64A4A")
        calibrated += 1
    if not calibrated:
        draw.rectangle((8, 8, min(image.width - 8, 520), 38), fill="#FFF4D6", outline="#B7791F")
        draw.text((16, 16), "Nenhuma região calibrada: revisão de coordenadas necessária", fill="#744210")
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue(), calibrated


def prepare_page_preflight(*, pdf_path, template, page_number, output_dir):
    """Renderiza, pré-processa e grava artefatos visuais/manifesto sem usar Gemini."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    original, render_info = render_pdf_page(pdf_path, page_number)
    processed = preprocess_image(original, "image/png")
    field_query = template.fields.all() if template.repeat_layout_per_page else template.fields.filter(page_number=page_number)
    page_fields = list(field_query.order_by("order", "field_id"))
    overlay, calibrated_count = draw_region_overlay(processed.data, page_fields)
    estimate = estimate_page_usage(processed.data, field_count=len(page_fields))
    (output_path / "pagina-original.png").write_bytes(original)
    (output_path / "pagina-preprocessada.png").write_bytes(processed.data)
    (output_path / "pagina-regioes.png").write_bytes(overlay)
    manifest = {
        "template": {"code": template.code, "version": template.version, "name": template.name},
        "page": page_number,
        "source_pdf": Path(pdf_path).name,
        "render": render_info,
        "preprocessing": {
            "quality_score": processed.quality_score,
            "warnings": processed.warnings,
            "rotation_degrees": processed.rotation_degrees,
            "perspective_corrected": processed.perspective_corrected,
        },
        "fields_total": len(page_fields),
        "fields_calibrated": calibrated_count,
        "fields_pending_calibration": [field.field_id for field in page_fields if not field.region],
        "estimated_usage": estimate,
        "real_api_call": False,
        "authorization_required": True,
    }
    (output_path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest, processed.data
