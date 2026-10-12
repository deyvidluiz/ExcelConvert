import hashlib
from pathlib import Path

from django.core.files import File
from django.db import transaction

from .catalog import DEFAULT_FIELDS, DEFAULT_TEMPLATE_CODE, DEFAULT_TEMPLATE_NAME
from .models import DocumentTemplate, TemplateField


@transaction.atomic
def register_cemig_template(*, reference_path=None, created_by=None, version="1.0.0"):
    template, _ = DocumentTemplate.objects.get_or_create(
        code=DEFAULT_TEMPLATE_CODE,
        version=version,
        defaults={
            "name": DEFAULT_TEMPLATE_NAME,
            "issuer": "CEMIG",
            "description": "Modelo versionado para fichas de ensaios de comissionamento de transformador de corrente.",
            "page_count": 9,
            "repeat_layout_per_page": True,
            "calibration_status": "pending",
            "created_by": created_by,
        },
    )
    template.name = DEFAULT_TEMPLATE_NAME
    template.issuer = "CEMIG"
    template.page_count = 9
    template.repeat_layout_per_page = True
    if created_by and not template.created_by_id:
        template.created_by = created_by
    if reference_path:
        path = Path(reference_path)
        data = path.read_bytes()
        try:
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz

            reference_page_count = len(fitz.open(stream=data, filetype="pdf"))
        except Exception:
            reference_page_count = None
        with path.open("rb") as reference_file:
            template.reference_pdf.save(path.name, File(reference_file), save=False)
        template.reference_sha256 = hashlib.sha256(data).hexdigest()
        if reference_page_count:
            template.page_count = reference_page_count
    template.save()
    for order, item in enumerate(DEFAULT_FIELDS, start=1):
        field_id, name, section, page, expected_type, required, location_hint, *rules = item
        TemplateField.objects.update_or_create(
            template=template,
            field_id=field_id,
            defaults={
                "name": name,
                "section": section,
                "page_number": page,
                "order": order,
                "location_hint": location_hint,
                "expected_type": expected_type,
                "required": required,
                "validation_rule": rules[0] if rules else "",
                "handwritten_priority": True,
            },
        )
    return template
