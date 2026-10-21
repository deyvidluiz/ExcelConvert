import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from extracao.gemini_service import PROVIDER_BUSY_MESSAGE, GeminiExtractionError
from extracao.services import (
    DocumentQualityError,
    ExtractionService,
    ExtractionServiceError,
    PreflightError,
    ProcessingInProgress,
)
from modelos.models import FieldRegionPreview

from .forms import MultiUploadForm
from .models import Document

logger = logging.getLogger(__name__)


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
                    template=form.cleaned_data.get("template"),
                )
            )
        messages.success(request, f"{len(created)} documento(s) recebido(s). Confirme o processamento.")
        return redirect("processamento", pk=created[0].pk)
    return render(request, "documentos/upload.html", {"form": form})


def _document_unavailable(request):
    """Página amigável para documento inexistente ou de outro proprietário.

    A resposta é idêntica nos dois casos: nada revela se o UUID existe para
    outra conta.
    """
    return render(request, "documentos/document_unavailable.html", status=404)


@login_required
@require_http_methods(["GET", "POST"])
def process_document(request, pk):
    # O filtro por proprietário é mantido; apenas a resposta de ausência deixa
    # de ser um 404 cru para virar uma página com saídas úteis.
    document = Document.objects.filter(pk=pk, user=request.user).first()
    if document is None:
        return _document_unavailable(request)
    if request.method == "POST":
        paid_confirmed = request.POST.get("confirm_paid") == "on"
        try:
            ExtractionService().process(document, paid_confirmed=paid_confirmed)
            messages.success(request, "Documento processado. Revise os dados antes de exportar.")
            return redirect("validacao:editor", pk=document.pk)
        except ProcessingInProgress as exc:
            # Submissão duplicada: o documento segue com o estado da execução
            # em andamento, por isso não há refresh nem mensagem de falha.
            messages.warning(request, str(exc))
        except GeminiExtractionError as exc:
            document.refresh_from_db()
            # Indisponibilidade do provedor não é erro do usuário nem do arquivo:
            # nenhuma repetição automática, apenas o convite a tentar de novo.
            if exc.transient:
                messages.warning(request, exc.user_message)
            else:
                messages.error(request, exc.user_message)
        except (DocumentQualityError, PreflightError) as exc:
            document.refresh_from_db()
            messages.error(request, str(exc))
        except ExtractionServiceError as exc:
            document.refresh_from_db()
            messages.error(request, f"Erro na extração: {exc}")
        except Exception as exc:
            logger.error(
                "Unexpected document processing failure: exception_type=%s message=%s",
                exc.__class__.__name__,
                str(exc),
            )
            document.refresh_from_db()
            messages.error(request, "Não foi possível processar o documento. Tente novamente ou solicite suporte.")
    return render(
        request,
        "documentos/processing.html",
        {
            "document": document,
            "provider_busy": document.status == Document.Status.FAILED
            and document.error_message == PROVIDER_BUSY_MESSAGE,
        },
    )


@login_required
def serve_document(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    if not document.file:
        raise Http404
    response = FileResponse(document.file.open("rb"), content_type=document.mime_type)
    response["Content-Disposition"] = f'inline; filename="{document.original_name}"'
    return response


@login_required
def serve_field_preview(request, pk, field_id):
    preview = get_object_or_404(FieldRegionPreview, document__pk=pk, document__user=request.user, field__field_id=field_id)
    return FileResponse(preview.image.open("rb"), content_type="image/png")


@login_required
@require_POST
def delete_document(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    document.delete()
    messages.success(request, "Documento excluído.")
    return redirect("historico")
