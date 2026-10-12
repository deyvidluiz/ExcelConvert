from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from extracao.services import ExtractionService

from .forms import MultiUploadForm
from .models import Document


@login_required
@require_http_methods(["GET", "POST"])
def upload(request):
    form = MultiUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        created = []
        for uploaded, inspected in zip(request.FILES.getlist("files"), form.cleaned_data["files"]):
            created.append(
                Document.objects.create(
                    user=request.user,
                    file=uploaded,
                    original_name=uploaded.name,
                    mime_type=inspected["mime_type"],
                    size_bytes=inspected["size_bytes"],
                    sha256=inspected["sha256"],
                    page_count=inspected["page_count"],
                )
            )
        messages.success(request, f"{len(created)} documento(s) recebido(s). Confirme o processamento.")
        return redirect("processamento", pk=created[0].pk)
    return render(request, "documentos/upload.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def process_document(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    if request.method == "POST":
        paid_confirmed = request.POST.get("confirm_paid") == "on"
        try:
            ExtractionService().process(document, paid_confirmed=paid_confirmed)
            messages.success(request, "Documento processado. Revise os dados antes de exportar.")
            return redirect("validacao:editor", pk=document.pk)
        except Exception as exc:
            document.refresh_from_db()
            messages.error(request, str(exc))
    return render(request, "documentos/processing.html", {"document": document})


@login_required
def serve_document(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    if not document.file:
        raise Http404
    response = FileResponse(document.file.open("rb"), content_type=document.mime_type)
    response["Content-Disposition"] = f'inline; filename="{document.original_name}"'
    return response


@login_required
@require_POST
def delete_document(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    document.file.delete(save=False)
    document.delete()
    messages.success(request, "Documento excluído.")
    return redirect("historico")
