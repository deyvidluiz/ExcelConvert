from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from documentos.models import Document

from .services import build_docx, build_pdf, build_xlsx, extraction_for


@login_required
def download(request, pk, format):
    document = get_object_or_404(Document, pk=pk, user=request.user, status=Document.Status.READY)
    payload = extraction_for(document)
    builders = {"xlsx": (build_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"), "docx": (build_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"), "pdf": (build_pdf, "application/pdf", ".pdf")}
    if format not in builders:
        return HttpResponse("Formato não suportado", status=400)
    builder, content_type, suffix = builders[format]
    response = HttpResponse(builder(payload).read(), content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{document.original_name.rsplit(".", 1)[0]}{suffix}"'
    return response
