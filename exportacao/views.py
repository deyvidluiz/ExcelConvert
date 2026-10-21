from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from documentos.models import Document

from .services import build_docx, build_pdf, build_xlsx, build_xlsx_from_template, extraction_for, style_config_for


@login_required
def download(request, pk, format):
    document = get_object_or_404(Document, pk=pk, user=request.user, status=Document.Status.READY)
    payload = extraction_for(document)
    builders = {"xlsx": (build_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"), "docx": (build_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"), "pdf": (build_pdf, "application/pdf", ".pdf")}
    if format not in builders:
        return HttpResponse("Formato não suportado", status=400)
    builder, content_type, suffix = builders[format]
    if format == "xlsx":
        excel_template = None
        if document.template_id:
            excel_template = document.template.excel_templates.filter(is_active=True).order_by("-created_at").first()
        if excel_template and "template_fields" in payload:
            # Prioridade 1: preencher o modelo Excel preservando seus estilos. Vale
            # também quando a extração não leu nenhum campo: a base é o modelo.
            builder = lambda data: build_xlsx_from_template(data, excel_template)
        else:
            # Sem campos mapeados, reconstrói o layout com os estilos do modelo.
            style_config = style_config_for(document)
            builder = lambda data: build_xlsx(data, style_config=style_config)
    else:
        # Word e PDF seguem a mesma paleta da planilha.
        style_config = style_config_for(document)
        builder = lambda data, build=builder: build(data, style_config=style_config)
    response = HttpResponse(builder(payload).read(), content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{document.original_name.rsplit(".", 1)[0]}{suffix}"'
    return response
